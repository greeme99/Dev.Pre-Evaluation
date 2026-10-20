"""Pixel RAG: multi-modal drawing tile to case image retrieval (FN-006, RET-005)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dev_pre_review.drawings.tiling import DrawingTile
from dev_pre_review.retrieval.visual_index import VisualEmbeddingProvider, VisualVectorStore


class VisualEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: UUID
    image_ref: str
    page_number: int
    pixel_bbox: tuple[float, float, float, float]
    visual_score: float
    text_score: float | None = None
    fused_score: float | None = None


class PixelRetriever:
    def __init__(
        self,
        visual_store: VisualVectorStore,
        visual_provider: VisualEmbeddingProvider,
    ) -> None:
        self.visual_store = visual_store
        self.visual_provider = visual_provider

    def search(
        self,
        tile: DrawingTile,
        project_id: UUID,
        top_k: int = 5,
    ) -> list[VisualEvidence]:
        # Embed the query tile image
        vectors = self.visual_provider.embed_images([tile.image_bytes])
        if not vectors:
            return []
        q_vec = vectors[0]

        results = self.visual_store.search(
            query_vector=q_vec,
            project_id=project_id,
            top_k=top_k,
        )

        tile_bbox = (
            float(tile.x),
            float(tile.y),
            float(tile.x + tile.width),
            float(tile.y + tile.height),
        )

        evidences: list[VisualEvidence] = []
        for r in results:
            t_score = r.text_score
            v_score = r.visual_score
            fused = 0.5 * v_score + 0.5 * t_score if t_score is not None else v_score

            evidences.append(
                VisualEvidence(
                    case_id=r.case_id,
                    image_ref=r.image_ref,
                    page_number=tile.page_number,
                    pixel_bbox=tile_bbox,
                    visual_score=v_score,
                    text_score=t_score,
                    fused_score=fused,
                )
            )

        return evidences
