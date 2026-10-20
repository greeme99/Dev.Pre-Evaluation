"""Tests for Pixel RAG, visual embedding, and tile-to-case image retrieval.
FN-006, RET-005, TC-017, TC-018.
"""

from uuid import uuid4

import pytest
from qdrant_client import QdrantClient

from dev_pre_review.drawings.tiling import DrawingTile
from dev_pre_review.retrieval.pixel_rag import PixelRetriever, VisualEvidence
from dev_pre_review.retrieval.visual_index import (
    DeterministicVisualEmbeddingProvider,
    VisualVectorStore,
)


@pytest.fixture
def visual_provider() -> DeterministicVisualEmbeddingProvider:
    return DeterministicVisualEmbeddingProvider(dimension=64)


@pytest.fixture
def visual_store(visual_provider: DeterministicVisualEmbeddingProvider) -> VisualVectorStore:
    client = QdrantClient(":memory:")
    store = VisualVectorStore(client, collection_name="visual_cases")
    store.ensure_collection(dimension=visual_provider.dimension)
    return store


@pytest.fixture
def pixel_retriever(
    visual_store: VisualVectorStore,
    visual_provider: DeterministicVisualEmbeddingProvider,
) -> PixelRetriever:
    return PixelRetriever(
        visual_store=visual_store,
        visual_provider=visual_provider,
    )


def test_pixel_retriever_indexes_case_images_and_retrieves_by_tile(
    pixel_retriever: PixelRetriever,
    visual_store: VisualVectorStore,
    visual_provider: DeterministicVisualEmbeddingProvider,
) -> None:
    p_id = uuid4()
    case1_id = uuid4()
    case2_id = uuid4()

    # Synthetic image bytes
    img1 = b"PNG_FAKE_IMAGE_DEFECT_1_HOLE_CRACK"
    img2 = b"PNG_FAKE_IMAGE_DEFECT_2_WIRING_FAULT"

    # Index case images
    vecs = visual_provider.embed_images([img1, img2])
    visual_store.upsert_case_images(
        [
            (case1_id, p_id, "image_ref_1", {"discipline": "mechanical", "text_score": 0.85}),
            (case2_id, p_id, "image_ref_2", {"discipline": "electrical", "text_score": 0.40}),
        ],
        vectors=vecs,
    )

    # Search using a drawing tile similar to img1
    query_tile = DrawingTile(
        tile_id=uuid4(),
        page_number=1,
        tile_index=0,
        x=100,
        y=200,
        width=512,
        height=512,
        image_bytes=img1,
    )

    results: list[VisualEvidence] = pixel_retriever.search(
        tile=query_tile,
        project_id=p_id,
        top_k=2,
    )

    assert len(results) >= 1
    top = results[0]
    assert top.case_id == case1_id
    assert top.image_ref == "image_ref_1"
    assert top.visual_score > 0.0
    assert top.text_score == 0.85
    # Check that pixel coordinates from the tile are preserved
    assert top.pixel_bbox == (100.0, 200.0, 612.0, 712.0)
    assert top.page_number == 1


def test_pixel_retriever_preserves_separate_text_and_visual_scores(
    pixel_retriever: PixelRetriever,
    visual_store: VisualVectorStore,
    visual_provider: DeterministicVisualEmbeddingProvider,
) -> None:
    p_id = uuid4()
    case_id = uuid4()
    img = b"PNG_SAMPLE_CASE"

    vecs = visual_provider.embed_images([img])
    visual_store.upsert_case_images(
        [(case_id, p_id, "ref_1", {"discipline": "mechanical", "text_score": 0.90})],
        vectors=vecs,
    )

    tile = DrawingTile(
        tile_id=uuid4(),
        page_number=2,
        tile_index=1,
        x=50,
        y=50,
        width=200,
        height=200,
        image_bytes=img,
    )

    evidences = pixel_retriever.search(tile=tile, project_id=p_id, top_k=1)
    assert len(evidences) == 1
    ev = evidences[0]
    assert ev.text_score == 0.90
    assert ev.visual_score is not None
    assert ev.fused_score is not None
    assert ev.pixel_bbox == (50.0, 50.0, 250.0, 250.0)
