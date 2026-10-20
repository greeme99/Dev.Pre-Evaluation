"""Tests for KnowledgeImporter: mapping commitment, idempotency, duplicate prevention."""

from pathlib import Path

import pytest
from conftest import Repos, Seed

from dev_pre_review.knowledge.excel_reader import ExcelReader
from dev_pre_review.knowledge.importer import (
    CommitRequest,
    ImportResult,
    KnowledgeImporter,
)

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "excel"


@pytest.fixture
def importer(database, repos: Repos) -> KnowledgeImporter:
    return KnowledgeImporter(database.sessions)


def test_commits_mapping_and_saves_cases(importer: KnowledgeImporter, seed: Seed) -> None:
    reader = ExcelReader()
    preview = reader.preview(FIXTURES_DIR / "standard.xlsx")

    commit_req = CommitRequest(
        project_id=seed.project.id,
        preview_id=preview.preview_id,
        file_sha256=preview.file_sha256,
        file_name=preview.file_name,
        sheet_name="오류사례",
        column_mapping={
            "부품명": "part_name",
            "오류설명": "description",
            "심각도": "severity",
            "조치사항": "action",
        },
        idempotency_key="commit-key-1",
    )

    result = importer.commit(commit_req, preview)

    assert isinstance(result, ImportResult)
    assert result.cases_imported == 2
    assert result.duplicate_count == 0

    cases = importer.list_cases_for_project(seed.project.id)
    assert len(cases) == 2
    assert any("가공 공차 누락" in c.text for c in cases)


def test_reimport_with_same_key_or_hash_prevents_duplicate_cases(
    importer: KnowledgeImporter, seed: Seed
) -> None:
    reader = ExcelReader()
    preview = reader.preview(FIXTURES_DIR / "standard.xlsx")

    commit_req = CommitRequest(
        project_id=seed.project.id,
        preview_id=preview.preview_id,
        file_sha256=preview.file_sha256,
        file_name=preview.file_name,
        sheet_name="오류사례",
        column_mapping={"오류설명": "description"},
        idempotency_key="commit-key-dup",
    )

    res1 = importer.commit(commit_req, preview)
    assert res1.cases_imported == 2

    # Second commit with same idempotency key or content
    res2 = importer.commit(commit_req, preview)
    assert res2.cases_imported == 0
    assert res2.duplicate_count == 2

    # Total cases in project should remain exactly 2
    cases = importer.list_cases_for_project(seed.project.id)
    assert len(cases) == 2
