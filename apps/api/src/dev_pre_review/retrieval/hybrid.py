"""Hybrid retriever combining SQLite FTS5 and Qdrant with RRF (FN-006, RET-004, TC-017, TC-018)."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dev_pre_review.models.embeddings import EmbeddingProvider
from dev_pre_review.retrieval.text_index import SQLiteTextIndex
from dev_pre_review.retrieval.vector_store import QdrantVectorStore


class RetrievedCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: UUID
    discipline: str
    error_type: str
    severity: str
    content: str
    score: float
    text_rank: int | None = None
    vector_rank: int | None = None


class HybridRetriever:
    def __init__(
        self,
        vector_store: QdrantVectorStore,
        text_index: SQLiteTextIndex,
        embedding_provider: EmbeddingProvider,
        rrf_k: int = 60,
    ) -> None:
        self.vector_store = vector_store
        self.text_index = text_index
        self.embedding_provider = embedding_provider
        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        project_id: UUID,
        discipline: str | None = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[RetrievedCase]:
        clean_q = query.strip()
        if not clean_q:
            return []

        # 1. Text keyword search (SQLite FTS5)
        candidate_multiplier = max(top_k * 3, 20)
        text_results = self.text_index.search(
            query=clean_q,
            project_id=project_id,
            discipline=discipline,
            top_k=candidate_multiplier,
        )

        # 2. Dense vector search (Qdrant)
        query_vectors = self.embedding_provider.embed_texts([clean_q])
        q_vec = query_vectors[0]
        vector_results = self.vector_store.search(
            query_vector=q_vec,
            project_id=project_id,
            discipline=discipline,
            top_k=candidate_multiplier,
        )

        # 3. Reciprocal Rank Fusion (RRF)
        # Score = sum(1 / (k + rank))
        scores: dict[UUID, float] = {}
        meta_map: dict[UUID, dict[str, Any]] = {}
        text_ranks: dict[UUID, int] = {}
        vector_ranks: dict[UUID, int] = {}

        for tr in text_results:
            cid = tr.case_id
            text_ranks[cid] = tr.rank
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (self.rrf_k + tr.rank))
            meta_map[cid] = {
                "discipline": tr.discipline,
                "error_type": tr.error_type,
                "severity": tr.severity,
                "content": tr.content,
            }

        for vr in vector_results:
            cid = vr.case_id
            vector_ranks[cid] = vr.rank
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (self.rrf_k + vr.rank))
            if cid not in meta_map:
                meta_map[cid] = {
                    "discipline": vr.discipline,
                    "error_type": vr.error_type,
                    "severity": vr.severity,
                    "content": vr.content,
                }

        # 4. Sort and threshold
        sorted_cases = sorted(scores.items(), key=lambda item: item[1], reverse=True)

        results: list[RetrievedCase] = []
        for cid, score in sorted_cases:
            if score < score_threshold:
                continue
            m = meta_map[cid]
            results.append(
                RetrievedCase(
                    case_id=cid,
                    discipline=m["discipline"],
                    error_type=m["error_type"],
                    severity=m["severity"],
                    content=m["content"],
                    score=score,
                    text_rank=text_ranks.get(cid),
                    vector_rank=vector_ranks.get(cid),
                )
            )
            if len(results) >= top_k:
                break

        return results
