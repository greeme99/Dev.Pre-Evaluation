"""Qdrant local vector store integration (FN-006, RET-003)."""

from typing import Any
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

from dev_pre_review.domain.models import KnowledgeCase


class VectorSearchResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: UUID
    project_id: UUID
    discipline: str
    error_type: str
    severity: str
    content: str
    score: float
    rank: int


class QdrantVectorStore:
    def __init__(self, client: QdrantClient, collection_name: str = "knowledge_cases") -> None:
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

    def upsert_cases(
        self,
        cases_with_meta: list[tuple[KnowledgeCase, dict[str, Any]]],
        vectors: list[list[float]],
        index_version: str = "v1.0",
    ) -> None:
        points: list[PointStruct] = []
        for (case, meta), vec in zip(cases_with_meta, vectors, strict=True):
            payload = {
                "case_id": str(case.id),
                "project_id": str(case.project_id),
                "discipline": meta.get("discipline", "general"),
                "error_type": meta.get("error_type", "unknown"),
                "severity": meta.get("severity", "medium"),
                "source_sheet": case.source_sheet,
                "source_cell": case.source_cell,
                "index_version": index_version,
                "content": case.text,
            }
            points.append(
                PointStruct(
                    id=str(case.id),
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
        discipline: str | None = None,
        top_k: int = 5,
    ) -> list[VectorSearchResult]:
        must_conditions: list[Any] = [
            FieldCondition(key="project_id", match=MatchValue(value=str(project_id)))
        ]
        if discipline:
            must_conditions.append(
                FieldCondition(key="discipline", match=MatchValue(value=discipline))
            )

        query_filter = Filter(must=must_conditions)

        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
        )

        results: list[VectorSearchResult] = []
        for rank, point in enumerate(res.points, start=1):
            p = point.payload or {}
            results.append(
                VectorSearchResult(
                    case_id=UUID(str(p.get("case_id", point.id))),
                    project_id=UUID(str(p.get("project_id", project_id))),
                    discipline=str(p.get("discipline", "general")),
                    error_type=str(p.get("error_type", "unknown")),
                    severity=str(p.get("severity", "medium")),
                    content=str(p.get("content", "")),
                    score=float(point.score if point.score is not None else 0.0),
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


class QdrantPurger:
    name = "qdrant"

    def __init__(self, vector_store: QdrantVectorStore) -> None:
        self.vector_store = vector_store

    def purge_project(self, project_id: UUID) -> None:
        self.vector_store.delete_by_project(project_id)
