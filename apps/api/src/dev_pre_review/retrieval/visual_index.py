"""Visual vector store and embedding provider for Pixel RAG (FN-006, RET-005)."""

import hashlib
import math
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)


class VisualSearchResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: UUID
    project_id: UUID
    image_ref: str
    discipline: str
    text_score: float | None = None
    visual_score: float
    rank: int


class VisualEmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed_images(self, images: list[bytes]) -> list[list[float]]: ...


class DeterministicVisualEmbeddingProvider:
    """Deterministic visual embedding provider for tests and reproducible verification."""

    def __init__(self, dimension: int = 64) -> None:
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_images(self, images: list[bytes]) -> list[list[float]]:
        return [self._embed_single(b) for b in images]

    def _embed_single(self, raw_bytes: bytes) -> list[float]:
        vec = [0.0] * self._dim
        if not raw_bytes:
            return vec

        chunk_size = max(1, len(raw_bytes) // self._dim)
        for i in range(self._dim):
            chunk = raw_bytes[i * chunk_size : (i + 1) * chunk_size]
            if chunk:
                val = sum(chunk) / len(chunk)
                h = int(hashlib.md5(chunk).hexdigest(), 16)  # noqa: S324
                vec[i] = val + (h % 100) / 100.0

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0.0:
            vec = [v / norm for v in vec]
        return vec


class VisualVectorStore:
    def __init__(self, client: QdrantClient, collection_name: str = "visual_cases") -> None:
        self.client = client
        self.collection_name = collection_name

    def ensure_collection(self, dimension: int) -> None:
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )

    def upsert_case_images(
        self,
        items: list[tuple[UUID, UUID, str, dict[str, Any]]],
        vectors: list[list[float]],
    ) -> None:
        points: list[PointStruct] = []
        for (case_id, project_id, image_ref, meta), vec in zip(items, vectors, strict=True):
            point_id = hashlib.md5(f"{case_id}_{image_ref}".encode()).hexdigest()  # noqa: S324
            payload = {
                "case_id": str(case_id),
                "project_id": str(project_id),
                "image_ref": image_ref,
                "discipline": meta.get("discipline", "general"),
                "text_score": meta.get("text_score"),
            }
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vec,
                    payload=payload,
                )
            )

        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )

    def search(
        self,
        query_vector: list[float],
        project_id: UUID,
        top_k: int = 5,
    ) -> list[VisualSearchResult]:
        query_filter = Filter(
            must=[FieldCondition(key="project_id", match=MatchValue(value=str(project_id)))]
        )

        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
        )

        results: list[VisualSearchResult] = []
        for rank, p in enumerate(res.points, start=1):
            payload = p.payload or {}
            results.append(
                VisualSearchResult(
                    case_id=UUID(str(payload.get("case_id"))),
                    project_id=UUID(str(payload.get("project_id", project_id))),
                    image_ref=str(payload.get("image_ref")),
                    discipline=str(payload.get("discipline", "general")),
                    text_score=payload.get("text_score"),
                    visual_score=float(p.score if p.score is not None else 0.0),
                    rank=rank,
                )
            )
        return results

    def delete_by_project(self, project_id: UUID) -> None:
        del_filter = Filter(
            must=[FieldCondition(key="project_id", match=MatchValue(value=str(project_id)))]
        )
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(filter=del_filter),
            wait=True,
        )
