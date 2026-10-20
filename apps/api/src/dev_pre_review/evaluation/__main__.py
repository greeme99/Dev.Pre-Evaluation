"""Retrieval evaluation runner (FN-006, TC-017, TC-018)."""

import sqlite3
import sys
from uuid import uuid4

from qdrant_client import QdrantClient

from dev_pre_review.domain.models import KnowledgeCase, Sha256, utc_now
from dev_pre_review.models.embeddings import DeterministicEmbeddingProvider
from dev_pre_review.retrieval.hybrid import HybridRetriever
from dev_pre_review.retrieval.pixel_rag import PixelRetriever
from dev_pre_review.retrieval.text_index import SQLiteTextIndex
from dev_pre_review.retrieval.visual_index import (
    DeterministicVisualEmbeddingProvider,
    VisualVectorStore,
)


def run_retrieval_evaluation() -> int:
    print("[Evaluation] Running retrieval benchmark on golden fixtures...")

    project_id = uuid4()
    text_emb = DeterministicEmbeddingProvider(dimension=64)
    visual_emb = DeterministicVisualEmbeddingProvider(dimension=64)

    # In-memory stores for clean benchmark
    conn = sqlite3.connect(":memory:")
    text_idx = SQLiteTextIndex(conn)
    text_idx.initialize()

    q_client = QdrantClient(":memory:")
    vec_store = QdrantClient(":memory:")
    from dev_pre_review.retrieval.vector_store import QdrantVectorStore

    v_store = QdrantVectorStore(q_client, collection_name="eval_text")
    v_store.ensure_collection(dimension=text_emb.dimension)

    visual_store = VisualVectorStore(vec_store, collection_name="eval_visual")
    visual_store.ensure_collection(dimension=visual_emb.dimension)

    hybrid = HybridRetriever(v_store, text_idx, text_emb, rrf_k=60)
    PixelRetriever(visual_store, visual_emb)

    # 1. Golden cases setup
    golden_cases = [
        ("case-1", "치수 공차 초과 가공 마진 부족 조립 불량", b"IMG_HOLE_CRACK", "mechanical"),
        ("case-2", "전기 제어반 배선 결선 오류 커넥터 단선", b"IMG_WIRING_FAULT", "electrical"),
        ("case-3", "배관 용접부 비파괴 검사 균열 결함", b"IMG_WELD_CRACK", "piping"),
        ("case-4", "도면 표제란 재질 표기 오류 SUS304 누락", b"IMG_TITLE_BLOCK", "mechanical"),
        ("case-5", "표면 거칠기 가공 조도 기준 초과 불량", b"IMG_SURFACE_ROUGH", "mechanical"),
    ]

    kc_list = []
    v_items = []
    img_bytes_list = []
    for cid_str, text, img_bytes, disc in golden_cases:
        cid = uuid4()
        kc = KnowledgeCase(
            id=cid,
            project_id=project_id,
            text=text,
            source_file_sha256=Sha256("0" * 64),
            source_sheet="Golden",
            source_cell="A1",
            created_at=utc_now(),
        )
        kc_list.append((kc, {"discipline": disc, "error_type": cid_str, "text_score": 0.9}))
        v_items.append((cid, project_id, f"ref_{cid_str}", {"discipline": disc, "text_score": 0.9}))
        img_bytes_list.append(img_bytes)

    # Index
    text_idx.upsert_cases(kc_list, index_version="golden_v1")
    t_vectors = text_emb.embed_texts([c.text for c, _ in kc_list])
    v_store.upsert_cases(kc_list, vectors=t_vectors, index_version="golden_v1")

    v_vectors = visual_emb.embed_images(img_bytes_list)
    visual_store.upsert_case_images(v_items, vectors=v_vectors)

    # 2. Run retrieval queries
    queries = [
        ("공차 초과 조립 불량", kc_list[0][0].id),
        ("제어반 배선 오류", kc_list[1][0].id),
        ("용접부 결함 균열", kc_list[2][0].id),
        ("표제란 재질 표기", kc_list[3][0].id),
        ("가공 조도 거칠기", kc_list[4][0].id),
    ]

    hits = 0
    for q, expected_id in queries:
        results = hybrid.search(q, project_id=project_id, top_k=5)
        matched_ids = [r.case_id for r in results]
        if expected_id in matched_ids:
            hits += 1

    recall_at_5 = hits / len(queries)
    print(
        f"[Evaluation] Hybrid Search Top-5 Recall: {recall_at_5 * 100:.1f}% ({hits}/{len(queries)})"
    )

    if recall_at_5 < 0.8:
        print("[Evaluation] FAILED: Top-5 recall below 80% gate.")
        return 1

    print("[Evaluation] SUCCESS: Top-5 retrieval gate passed (>= 80%).")
    return 0


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "retrieval":
        code = run_retrieval_evaluation()
        sys.exit(code)
    else:
        print(f"Unknown evaluation target: {args[0]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
