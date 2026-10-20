"""Tests for RuleEvaluator: deterministic evaluation, operators, units, and fault isolation.

FN-005, RULE-002~RULE-009, TC-013~TC-016.
"""

from uuid import uuid4

import pytest

from dev_pre_review.domain.enums import (
    DrawingType,
    EvidenceKind,
    FindingStatus,
    RuleOperator,
    RuleState,
    Severity,
)
from dev_pre_review.domain.models import RuleDefinition
from dev_pre_review.drawings.contracts import DrawingDocument, TextRegion
from dev_pre_review.rules.engine import RuleEvaluator


@pytest.fixture
def evaluator() -> RuleEvaluator:
    return RuleEvaluator()


def make_rule(
    field: str,
    operator: RuleOperator,
    value: str,
    unit: str | None = None,
    severity: Severity = Severity.HIGH,
) -> RuleDefinition:
    return RuleDefinition(
        id=uuid4(),
        project_id=uuid4(),
        drawing_types=(DrawingType.PDF, DrawingType.DXF),
        field=field,
        operator=operator,
        value=value,
        unit=unit,
        severity=severity,
        state=RuleState.APPROVED,
        version=1,
    )


def test_evaluator_checks_required_rule(evaluator: RuleEvaluator) -> None:
    rule = make_rule("material", RuleOperator.REQUIRED, "true")

    # Document without material
    doc_empty = DrawingDocument(
        drawing_id=uuid4(),
        drawing_type=DrawingType.PDF,
        file_name="empty.pdf",
        file_sha256="0" * 64,
        page_count=1,
        regions=[TextRegion(page_or_sheet=1, raw_text="도면명: 부품도", confidence=1.0)],
    )

    result = evaluator.evaluate(doc_empty, [rule])
    assert len(result.findings) == 1
    f = result.findings[0]
    assert f.status == FindingStatus.VIOLATION
    assert any(e.kind == EvidenceKind.RULE and e.ref_id == str(rule.id) for e in f.evidence)
    assert "required" in f.message.lower()

    # Document with material
    doc_with_mat = DrawingDocument(
        drawing_id=uuid4(),
        drawing_type=DrawingType.PDF,
        file_name="valid.pdf",
        file_sha256="0" * 64,
        page_count=1,
        regions=[TextRegion(page_or_sheet=1, raw_text="재질: SUS304", confidence=1.0)],
    )
    result_valid = evaluator.evaluate(doc_with_mat, [rule])
    assert len(result_valid.findings) == 0


def test_evaluator_checks_max_numeric_with_unit_conversion(evaluator: RuleEvaluator) -> None:
    # Rule specifies max tolerance 0.02 mm
    rule = make_rule("tolerance", RuleOperator.MAX, "0.02", unit="mm")

    # Document specifies 0.05 mm -> exceeds 0.02 mm -> VIOLATION
    doc_viol = DrawingDocument(
        drawing_id=uuid4(),
        drawing_type=DrawingType.PDF,
        file_name="viol.pdf",
        file_sha256="0" * 64,
        page_count=1,
        regions=[
            TextRegion(
                page_or_sheet=1,
                raw_text="공차: +-0.05 mm",
                pixel_bbox=(100.0, 100.0, 200.0, 150.0),
                confidence=1.0,
            )
        ],
    )
    res_viol = evaluator.evaluate(doc_viol, [rule])
    assert len(res_viol.findings) == 1
    assert res_viol.findings[0].status == FindingStatus.VIOLATION
    assert len(res_viol.evidences) >= 1
    assert any(e.kind == EvidenceKind.RULE and e.ref_id == str(rule.id) for e in res_viol.evidences)
    assert res_viol.findings[0].pixel_bbox == (100.0, 100.0, 200.0, 150.0)

    # Document specifies 15 um (= 0.015 mm) -> <= 0.02 mm -> PASS
    doc_pass = DrawingDocument(
        drawing_id=uuid4(),
        drawing_type=DrawingType.PDF,
        file_name="pass.pdf",
        file_sha256="0" * 64,
        page_count=1,
        regions=[
            TextRegion(
                page_or_sheet=1,
                raw_text="공차: +-15 um",
                pixel_bbox=(100.0, 100.0, 200.0, 150.0),
                confidence=1.0,
            )
        ],
    )
    res_pass = evaluator.evaluate(doc_pass, [rule])
    assert len(res_pass.findings) == 0


def test_evaluator_flags_insufficient_information_on_missing_unit(evaluator: RuleEvaluator) -> None:
    rule = make_rule("tolerance", RuleOperator.MAX, "0.02", unit="mm")

    # Document specifies 0.05 but unit is missing or unknown
    doc_no_unit = DrawingDocument(
        drawing_id=uuid4(),
        drawing_type=DrawingType.PDF,
        file_name="no_unit.pdf",
        file_sha256="0" * 64,
        page_count=1,
        regions=[
            TextRegion(
                page_or_sheet=1,
                raw_text="공차: +-0.05 (단위누락)",
                confidence=1.0,
            )
        ],
    )
    res = evaluator.evaluate(doc_no_unit, [rule])
    assert len(res.findings) == 1
    assert res.findings[0].status == FindingStatus.INSUFFICIENT_INFORMATION


def test_evaluator_flags_insufficient_information_on_quality_blocked(
    evaluator: RuleEvaluator,
) -> None:
    rule = make_rule("material", RuleOperator.EQUALS, "SUS304")

    # Document is marked quality_blocked due to missing XREF
    doc_blocked = DrawingDocument(
        drawing_id=uuid4(),
        drawing_type=DrawingType.DXF,
        file_name="blocked.dxf",
        file_sha256="0" * 64,
        page_count=1,
        regions=[],
        metadata={"quality_blocked": True, "missing_xrefs": ["ref.dwg"]},
    )
    res = evaluator.evaluate(doc_blocked, [rule])
    assert len(res.findings) == 1
    assert res.findings[0].status == FindingStatus.INSUFFICIENT_INFORMATION
    assert "quality blocked" in res.findings[0].message.lower()


def test_evaluator_isolates_rule_evaluation_errors(evaluator: RuleEvaluator) -> None:
    # Rule 1 has faulty regex pattern
    faulty_rule = make_rule("code", RuleOperator.MATCHES, "[invalid(regex")
    # Rule 2 is normal valid rule
    valid_rule = make_rule("material", RuleOperator.REQUIRED, "true")

    doc = DrawingDocument(
        drawing_id=uuid4(),
        drawing_type=DrawingType.PDF,
        file_name="test.pdf",
        file_sha256="0" * 64,
        page_count=1,
        regions=[TextRegion(page_or_sheet=1, raw_text="code: 12345", confidence=1.0)],
    )

    # Fault in Rule 1 should be isolated (yields INSUFFICIENT_INFORMATION or error finding),
    # while Rule 2 executes successfully
    res = evaluator.evaluate(doc, [faulty_rule, valid_rule])
    assert len(res.findings) >= 1
    # Check that evaluation completed without crashing
