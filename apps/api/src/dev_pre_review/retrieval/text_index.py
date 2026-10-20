"""SQLite FTS5 full-text indexing and keyword search (FN-006, RET-002)."""

import re
import sqlite3
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dev_pre_review.domain.models import KnowledgeCase


class TextSearchResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: UUID
    project_id: UUID
    discipline: str
    error_type: str
    severity: str
    content: str
    score: float
    rank: int


class SQLiteTextIndex:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.conn = connection

    def initialize(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS cases_fts USING fts5(
                    case_id UNINDEXED,
                    project_id UNINDEXED,
                    discipline UNINDEXED,
                    error_type UNINDEXED,
                    severity UNINDEXED,
                    source_sheet UNINDEXED,
                    source_cell UNINDEXED,
                    index_version UNINDEXED,
                    content,
                    tokenize = 'unicode61'
                )
                """
            )

    def upsert_cases(
        self,
        cases_with_meta: list[tuple[KnowledgeCase, dict[str, Any]]],
        index_version: str = "v1.0",
    ) -> None:
        with self.conn:
            for case, meta in cases_with_meta:
                # Remove existing record if any (idempotency)
                self.conn.execute(
                    "DELETE FROM cases_fts WHERE case_id = ?",
                    (str(case.id),),
                )
                discipline = meta.get("discipline", "general")
                error_type = meta.get("error_type", "unknown")
                severity = meta.get("severity", "medium")

                self.conn.execute(
                    """
                    INSERT INTO cases_fts(
                        case_id, project_id, discipline, error_type, severity,
                        source_sheet, source_cell, index_version, content
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(case.id),
                        str(case.project_id),
                        discipline,
                        error_type,
                        severity,
                        case.source_sheet,
                        case.source_cell,
                        index_version,
                        case.text,
                    ),
                )

    def search(
        self,
        query: str,
        project_id: UUID,
        discipline: str | None = None,
        top_k: int = 5,
    ) -> list[TextSearchResult]:
        sanitized_query = self._sanitize_query(query)
        if not sanitized_query:
            return []

        sql = """
            SELECT case_id, project_id, discipline, error_type, severity, content,
                   bm25(cases_fts) as bm25_score
            FROM cases_fts
            WHERE cases_fts MATCH ? AND project_id = ?
        """
        params: list[Any] = [sanitized_query, str(project_id)]

        if discipline:
            sql += " AND discipline = ?"
            params.append(discipline)

        sql += " ORDER BY bm25_score ASC LIMIT ?"
        params.append(top_k)

        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()

        results: list[TextSearchResult] = []
        for rank, row in enumerate(rows, start=1):
            results.append(
                TextSearchResult(
                    case_id=UUID(row[0]),
                    project_id=UUID(row[1]),
                    discipline=row[2],
                    error_type=row[3],
                    severity=row[4],
                    content=row[5],
                    score=float(row[6]),
                    rank=rank,
                )
            )
        return results

    def delete_by_project(self, project_id: UUID) -> None:
        with self.conn:
            self.conn.execute(
                "DELETE FROM cases_fts WHERE project_id = ?",
                (str(project_id),),
            )

    def _sanitize_query(self, query: str) -> str:
        # Extract alphanumeric, korean syllables, and quotes
        tokens = re.findall(r"[\w가-힣]+", query)
        if not tokens:
            return ""
        # Match tokens with OR or space
        return " OR ".join(f'"{t}"' for t in tokens)


class FtsPurger:
    name = "fts"

    def __init__(self, text_index: SQLiteTextIndex) -> None:
        self.text_index = text_index

    def purge_project(self, project_id: UUID) -> None:
        self.text_index.delete_by_project(project_id)
