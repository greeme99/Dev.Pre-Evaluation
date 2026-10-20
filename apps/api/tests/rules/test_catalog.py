"""Tests for RuleCandidateExtractor and RuleCatalog: transitions, validation, version lock."""

from uuid import uuid4

import pytest
from conftest import Seed

from dev_pre_review.domain.enums import DrawingType, RuleOperator, RuleState, Severity
from dev_pre_review.domain.errors import InvalidStateTransition, VersionConflict
from dev_pre_review.domain.models import KnowledgeCase
from dev_pre_review.rules.candidates import RuleCandidateExtractor
from dev_pre_review.rules.catalog import RuleCatalog, RuleValidationError
from dev_pre_review.rules.contracts import RuleCandidate


@pytest.fixture
def catalog(database) -> RuleCatalog:
    return RuleCatalog(database.sessions)


def test_extracts_deterministic_rule_candidates_from_cases(seed: Seed) -> None:
    extractor = RuleCandidateExtractor()

    case1 = KnowledgeCase(
        project_id=seed.project.id,
        text="가공 공차 누락 (공차 기준 +-0.05 mm 필요)",
        source_file_sha256="0" * 64,
        source_sheet="시트1",
        source_cell="B2",
    )
    candidates1 = extractor.extract(case1)
    assert len(candidates1) >= 1
    tol_cand = candidates1[0]
    assert tol_cand.field == "tolerance"
    assert tol_cand.value == "0.05"
    assert tol_cand.unit == "mm"
    assert tol_cand.operator in (RuleOperator.MAX, RuleOperator.RANGE)

    case2 = KnowledgeCase(
        project_id=seed.project.id,
        text="재질 표기 오류 (재질 SUS304 필요)",
        source_file_sha256="0" * 64,
        source_sheet="시트1",
        source_cell="B3",
    )
    candidates2 = extractor.extract(case2)
    assert len(candidates2) >= 1
    mat_cand = candidates2[0]
    assert mat_cand.field == "material"
    assert mat_cand.value == "SUS304"
    assert mat_cand.operator == RuleOperator.EQUALS


def test_rule_state_transitions_from_draft_to_approved_to_inactive(
    catalog: RuleCatalog, seed: Seed
) -> None:
    candidate = RuleCandidate(
        project_id=seed.project.id,
        drawing_types=(DrawingType.PDF, DrawingType.DXF),
        field="tolerance",
        operator=RuleOperator.MAX,
        value="0.05",
        unit="mm",
        severity=Severity.HIGH,
        source_case_ids=(uuid4(),),
    )

    rule = catalog.add_candidate(candidate)
    assert rule.state == RuleState.DRAFT
    assert rule.version == 1

    # draft -> approved
    approved = catalog.transition(rule.id, target_state=RuleState.APPROVED, expected_version=1)
    assert approved.state == RuleState.APPROVED
    assert approved.version == 2

    # approved -> inactive
    inactive = catalog.transition(rule.id, target_state=RuleState.INACTIVE, expected_version=2)
    assert inactive.state == RuleState.INACTIVE
    assert inactive.version == 3

    # inactive -> draft direct transition should be rejected
    with pytest.raises(InvalidStateTransition):
        catalog.transition(rule.id, target_state=RuleState.DRAFT, expected_version=3)


def test_approval_rejects_numeric_rule_with_missing_unit(catalog: RuleCatalog, seed: Seed) -> None:
    candidate = RuleCandidate(
        project_id=seed.project.id,
        drawing_types=(DrawingType.PDF,),
        field="tolerance",
        operator=RuleOperator.MAX,
        value="0.05",
        unit=None,  # Missing unit for numeric field!
        severity=Severity.HIGH,
        source_case_ids=(uuid4(),),
    )

    rule = catalog.add_candidate(candidate)

    with pytest.raises(RuleValidationError, match="unit required"):
        catalog.transition(rule.id, target_state=RuleState.APPROVED, expected_version=1)


def test_approval_rejects_rule_without_source_cases(catalog: RuleCatalog, seed: Seed) -> None:
    candidate = RuleCandidate(
        project_id=seed.project.id,
        drawing_types=(DrawingType.PDF,),
        field="layer",
        operator=RuleOperator.EQUALS,
        value="TEXT",
        unit=None,
        severity=Severity.MEDIUM,
        source_case_ids=(),  # No source case!
    )

    rule = catalog.add_candidate(candidate)

    with pytest.raises(RuleValidationError, match="source required"):
        catalog.transition(rule.id, target_state=RuleState.APPROVED, expected_version=1)


def test_optimistic_concurrency_rejects_stale_expected_version(
    catalog: RuleCatalog, seed: Seed
) -> None:
    candidate = RuleCandidate(
        project_id=seed.project.id,
        drawing_types=(DrawingType.PDF,),
        field="material",
        operator=RuleOperator.EQUALS,
        value="AL6061",
        unit=None,
        severity=Severity.LOW,
        source_case_ids=(uuid4(),),
    )

    rule = catalog.add_candidate(candidate)

    # Stale version 99 passed
    with pytest.raises(VersionConflict):
        catalog.transition(rule.id, target_state=RuleState.APPROVED, expected_version=99)
