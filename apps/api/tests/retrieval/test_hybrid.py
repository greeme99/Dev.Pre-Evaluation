"""Tests for HybridRetriever, QdrantVectorStore, and RRF rank fusion.

FN-006, RET-001~RET-005, TC-017, TC-018.
"""

import sqlite3
from uuid import UUID, uuid4

import pytest
from qdrant_client import QdrantClient

from dev_pre_review.domain.enums import ProjectStatus
from dev_pre_review.domain.models import KnowledgeCase, ReviewProject, Sha256, utc_now
from dev_pre_review.models.embeddings import DeterministicEmbeddingProvider
from dev_pre_review.retrieval.hybrid import HybridRetriever
from dev_pre_review.retrieval.text_index import FtsPurger, SQLiteTextIndex
from dev_pre_review.retrieval.vector_store import QdrantPurger, QdrantVectorStore
from dev_pre_review.storage.deletion import ProjectDeletionService


@pytest.fixture
def embedding_provider() -> DeterministicEmbeddingProvider:
    return DeterministicEmbeddingProvider(dimension=64)


@pytest.fixture
def vector_store(embedding_provider: DeterministicEmbeddingProvider) -> QdrantVectorStore:
    client = QdrantClient(":memory:")
    store = QdrantVectorStore(client, collection_name="test_cases")
    store.ensure_collection(dimension=embedding_provider.dimension)
    return store


@pytest.fixture
def text_index() -> SQLiteTextIndex:
    conn = sqlite3.connect(":memory:")
    index = SQLiteTextIndex(conn)
    index.initialize()
    return index


@pytest.fixture
def retriever(
    vector_store: QdrantVectorStore,
    text_index: SQLiteTextIndex,
    embedding_provider: DeterministicEmbeddingProvider,
) -> HybridRetriever:
    return HybridRetriever(
        vector_store=vector_store,
        text_index=text_index,
        embedding_provider=embedding_provider,
        rrf_k=60,
    )


def make_case(
    project_id,
    text: str,
    sheet: str = "Sheet1",
    cell: str = "A1",
) -> KnowledgeCase:
    return KnowledgeCase(
        id=uuid4(),
        project_id=project_id,
        text=text,
        source_file_sha256=Sha256("0" * 64),
        source_sheet=sheet,
        source_cell=cell,
        created_at=utc_now(),
    )


def test_hybrid_retriever_combines_text_and_vector_with_rrf(
    retriever: HybridRetriever,
    vector_store: QdrantVectorStore,
    text_index: SQLiteTextIndex,
    embedding_provider: DeterministicEmbeddingProvider,
) -> None:
    p_id = uuid4()
    c1 = make_case(p_id, "치수 공차 초과: 가공 마진 부족으로 인한 조립 불량")
    c2 = make_case(p_id, "볼트 체결부 홀 직경 치수 누락")
    c3 = make_case(p_id, "전기 케이블 피복 손상 및 단선 위험")

    cases = [
        (c1, {"discipline": "mechanical", "error_type": "tolerance", "severity": "high"}),
        (c2, {"discipline": "mechanical", "error_type": "missing_dim", "severity": "medium"}),
        (c3, {"discipline": "electrical", "error_type": "cable", "severity": "high"}),
    ]

    # Index into text and vector stores
    text_index.upsert_cases(cases, index_version="v1.0")

    texts = [c.text for c, _ in cases]
    vectors = embedding_provider.embed_texts(texts)
    vector_store.upsert_cases(cases, vectors=vectors, index_version="v1.0")

    # Search for "공차 초과 조립 불량"
    results = retriever.search(
        query="공차 초과 조립 불량",
        project_id=p_id,
        top_k=2,
    )

    assert len(results) >= 1
    top = results[0]
    assert top.case_id == c1.id
    assert top.discipline == "mechanical"
    assert top.error_type == "tolerance"
    # RRF score should be positive and bounded by 2 / (60 + 1)
    assert 0.0 < top.score <= 2.0 / 61.0
    assert top.text_rank is not None or top.vector_rank is not None


def test_hybrid_retriever_applies_score_threshold(
    retriever: HybridRetriever,
    vector_store: QdrantVectorStore,
    text_index: SQLiteTextIndex,
    embedding_provider: DeterministicEmbeddingProvider,
) -> None:
    p_id = uuid4()
    c1 = make_case(p_id, "치수 공차 초과 가공 불량")
    cases = [(c1, {"discipline": "mechanical", "error_type": "tolerance"})]

    text_index.upsert_cases(cases, index_version="v1.0")
    vectors = embedding_provider.embed_texts([c1.text])
    vector_store.upsert_cases(cases, vectors=vectors, index_version="v1.0")

    # High threshold filters out
    results_filtered = retriever.search(
        query="치수",
        project_id=p_id,
        score_threshold=0.99,  # RRF score is typically ~ 0.01 ~ 0.03
    )
    assert len(results_filtered) == 0

    # Low threshold includes
    results_included = retriever.search(
        query="치수",
        project_id=p_id,
        score_threshold=0.001,
    )
    assert len(results_included) == 1


def test_qdrant_purger_removes_project_vectors(
    vector_store: QdrantVectorStore,
    embedding_provider: DeterministicEmbeddingProvider,
) -> None:
    p1 = uuid4()
    p2 = uuid4()
    c1 = make_case(p1, "프로젝트 1번")
    c2 = make_case(p2, "프로젝트 2번")

    vectors = embedding_provider.embed_texts([c1.text, c2.text])
    vector_store.upsert_cases(
        [(c1, {"discipline": "mechanical"}), (c2, {"discipline": "electrical"})],
        vectors=vectors,
        index_version="v1.0",
    )

    purger = QdrantPurger(vector_store)
    assert purger.name == "qdrant"
    purger.purge_project(p1)

    # Search project 1 should return empty
    q_vec = embedding_provider.embed_texts(["프로젝트"])[0]
    res_p1 = vector_store.search(q_vec, project_id=p1)
    res_p2 = vector_store.search(q_vec, project_id=p2)

    assert len(res_p1) == 0
    assert len(res_p2) == 1


def test_deletion_service_integrates_qdrant_and_fts_purgers(
    vector_store: QdrantVectorStore,
    text_index: SQLiteTextIndex,
    embedding_provider: DeterministicEmbeddingProvider,
) -> None:
    class DummyProjects:
        def __init__(self) -> None:
            self.projects: dict[UUID, ReviewProject] = {}

        def get(self, project_id: UUID) -> ReviewProject:
            return self.projects[project_id]

        def update(self, project: ReviewProject) -> None:
            self.projects[project.id] = project

        def delete(self, project_id: UUID) -> None:
            self.projects.pop(project_id, None)

    class DummyJobs:
        def count_running_for_project(self, project_id: UUID) -> int:
            return 0

        def cancel_queued_for_project(self, project_id: UUID) -> None:
            pass

    p1 = uuid4()
    projects = DummyProjects()
    projects.projects[p1] = ReviewProject(
        id=p1,
        name="Proj 1",
        status=ProjectStatus.ACTIVE,
        created_at=utc_now(),
    )
    jobs = DummyJobs()

    c1 = make_case(p1, "프로젝트 1번 지식")
    text_index.upsert_cases([(c1, {"discipline": "mechanical"})])
    vector_store.upsert_cases(
        [(c1, {"discipline": "mechanical"})],
        vectors=embedding_provider.embed_texts([c1.text]),
    )

    deletion_service = ProjectDeletionService(
        projects=projects,  # type: ignore[arg-type]
        jobs=jobs,  # type: ignore[arg-type]
        purgers=[QdrantPurger(vector_store), FtsPurger(text_index)],
    )
    deletion_service.delete(p1)

    assert len(text_index.search("지식", project_id=p1)) == 0
    q_vec = embedding_provider.embed_texts(["지식"])[0]
    assert len(vector_store.search(q_vec, project_id=p1)) == 0
