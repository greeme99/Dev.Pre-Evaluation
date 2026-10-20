"""Tests for SQLite FTS5 text indexing and keyword search (FN-006, RET-001~RET-004, TC-017)."""

import sqlite3
from uuid import uuid4

import pytest

from dev_pre_review.domain.models import KnowledgeCase, Sha256, utc_now
from dev_pre_review.retrieval.text_index import FtsPurger, SQLiteTextIndex


@pytest.fixture
def fts_index() -> SQLiteTextIndex:
    conn = sqlite3.connect(":memory:")
    index = SQLiteTextIndex(conn)
    index.initialize()
    return index


def make_case(
    project_id,
    text: str,
    source_sheet: str = "Sheet1",
    source_cell: str = "B5",
) -> KnowledgeCase:
    return KnowledgeCase(
        id=uuid4(),
        project_id=project_id,
        text=text,
        source_file_sha256=Sha256("0" * 64),
        source_sheet=source_sheet,
        source_cell=source_cell,
        created_at=utc_now(),
    )


def test_text_index_upsert_and_keyword_search(fts_index: SQLiteTextIndex) -> None:
    p_id = uuid4()
    case1 = make_case(p_id, "기계 가공 공차 초과 불량 사례: 홀 직경 0.05mm 초과")
    case2 = make_case(p_id, "전기 제어반 배선 결선 오류 및 커넥터 체결 누락")
    case3 = make_case(p_id, "배관 용접부 비파괴 검사 결함: 균열 발생")

    # Upsert cases with metadata
    fts_index.upsert_cases(
        [
            (case1, {"discipline": "mechanical", "error_type": "tolerance"}),
            (case2, {"discipline": "electrical", "error_type": "wiring"}),
            (case3, {"discipline": "piping", "error_type": "welding"}),
        ],
        index_version="v1.0",
    )

    # Search for "공차"
    results = fts_index.search(query="공차", project_id=p_id, top_k=5)
    assert len(results) == 1
    assert results[0].case_id == case1.id
    assert results[0].discipline == "mechanical"
    assert results[0].error_type == "tolerance"
    assert results[0].rank == 1

    # Search for "오류"
    results_elec = fts_index.search(query="오류", project_id=p_id, top_k=5)
    assert len(results_elec) == 1
    assert results_elec[0].case_id == case2.id


def test_text_index_is_idempotent_on_reupsert(fts_index: SQLiteTextIndex) -> None:
    p_id = uuid4()
    case = make_case(p_id, "기존 설명 텍스트")
    fts_index.upsert_cases(
        [(case, {"discipline": "mechanical", "error_type": "initial"})],
        index_version="v1.0",
    )

    # Re-upsert with updated content
    case_updated = make_case(p_id, "수정된 설명 텍스트: 업데이트 완료")
    # Same ID
    case_updated = case_updated.model_copy(update={"id": case.id})

    fts_index.upsert_cases(
        [(case_updated, {"discipline": "mechanical", "error_type": "updated"})],
        index_version="v1.1",
    )

    results = fts_index.search(query="업데이트", project_id=p_id, top_k=5)
    assert len(results) == 1
    assert results[0].case_id == case.id
    assert results[0].error_type == "updated"

    # Old text should not match
    results_old = fts_index.search(query="기존", project_id=p_id, top_k=5)
    assert len(results_old) == 0


def test_text_index_discipline_filtering(fts_index: SQLiteTextIndex) -> None:
    p_id = uuid4()
    case_mech = make_case(p_id, "표면 거칠기 가공 불량 발생")
    case_elec = make_case(p_id, "표면 절연 코팅 불량 발생")

    fts_index.upsert_cases(
        [
            (case_mech, {"discipline": "mechanical", "error_type": "surface"}),
            (case_elec, {"discipline": "electrical", "error_type": "insulation"}),
        ],
        index_version="v1.0",
    )

    # Search with discipline filter
    results_mech = fts_index.search(
        query="불량",
        project_id=p_id,
        discipline="mechanical",
        top_k=5,
    )
    assert len(results_mech) == 1
    assert results_mech[0].case_id == case_mech.id

    results_elec = fts_index.search(
        query="불량",
        project_id=p_id,
        discipline="electrical",
        top_k=5,
    )
    assert len(results_elec) == 1
    assert results_elec[0].case_id == case_elec.id


def test_text_index_purger_deletes_project_rows(fts_index: SQLiteTextIndex) -> None:
    p1 = uuid4()
    p2 = uuid4()
    c1 = make_case(p1, "프로젝트 1번 지식 사례")
    c2 = make_case(p2, "프로젝트 2번 지식 사례")

    fts_index.upsert_cases(
        [(c1, {"discipline": "mechanical"}), (c2, {"discipline": "electrical"})],
        index_version="v1.0",
    )

    purger = FtsPurger(fts_index)
    assert purger.name == "fts"
    purger.purge_project(p1)

    assert len(fts_index.search("지식", project_id=p1)) == 0
    assert len(fts_index.search("지식", project_id=p2)) == 1
