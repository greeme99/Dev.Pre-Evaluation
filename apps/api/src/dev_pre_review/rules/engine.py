"""Deterministic rule evaluation engine (FN-005, RULE-002~RULE-009, TC-013~TC-016)."""

import re
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from dev_pre_review.domain.enums import EvidenceKind, FindingStatus, RuleOperator, Severity
from dev_pre_review.domain.models import Evidence, Finding, RuleDefinition, utc_now
from dev_pre_review.drawings.contracts import DrawingDocument, TextRegion
from dev_pre_review.rules.units import UnitConversionError, convert_unit

NUMERIC_PATTERN = re.compile(r"(?:[±\+\-]+\s*)?(\d+(?:\.\d+)?)\s*([a-zA-Z가-힣]+)?")


class RuleEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: list[Finding]
    evidences: list[Evidence] = Field(default_factory=list)


class RuleEvaluator:
    def evaluate(
        self,
        doc: DrawingDocument,
        rules: list[RuleDefinition],
        job_id: UUID | None = None,
    ) -> RuleEvaluationResult:
        actual_job_id = job_id or uuid4()
        now = utc_now()

        findings: list[Finding] = []
        all_evidences: list[Evidence] = []

        # Check if entire document is quality blocked (e.g. missing XREF)
        if doc.metadata.get("quality_blocked") is True:
            reasons = doc.metadata.get("missing_xrefs", [])
            msg = f"Drawing quality blocked due to missing external references: {reasons}"
            finding = Finding(
                job_id=actual_job_id,
                status=FindingStatus.INSUFFICIENT_INFORMATION,
                severity=Severity.HIGH,
                confidence=1.0,
                finding_type="quality_blocked",
                location="document",
                message=msg,
                created_at=now,
            )
            return RuleEvaluationResult(findings=[finding], evidences=[])

        # Evaluate each rule independently (fault isolated)
        for rule in rules:
            try:
                f_list, e_list = self._evaluate_single_rule(doc, rule, actual_job_id)
                findings.extend(f_list)
                all_evidences.extend(e_list)
            except Exception as exc:
                # Isolated rule error
                err_finding = Finding(
                    job_id=actual_job_id,
                    status=FindingStatus.INSUFFICIENT_INFORMATION,
                    severity=rule.severity,
                    confidence=1.0,
                    finding_type="evaluation_error",
                    location="rule_evaluator",
                    message=f"Evaluation error on rule {rule.id} ({rule.field}): {exc}",
                    evidence=(
                        Evidence(
                            kind=EvidenceKind.RULE,
                            ref_id=str(rule.id),
                            location="rule_definition",
                        ),
                    ),
                    created_at=now,
                )
                findings.append(err_finding)

        return RuleEvaluationResult(findings=findings, evidences=all_evidences)

    def _evaluate_single_rule(
        self, doc: DrawingDocument, rule: RuleDefinition, job_id: UUID
    ) -> tuple[list[Finding], list[Evidence]]:
        now = utc_now()
        matching_regions = self._find_matching_regions(doc, rule.field)

        # 1. Operator: REQUIRED
        if rule.operator == RuleOperator.REQUIRED:
            if not matching_regions:
                rule_ev = Evidence(
                    kind=EvidenceKind.RULE,
                    ref_id=str(rule.id),
                    location="rule_definition",
                )
                finding = Finding(
                    job_id=job_id,
                    status=FindingStatus.VIOLATION,
                    severity=rule.severity,
                    confidence=1.0,
                    finding_type="required_field_missing",
                    location=f"drawing:{doc.file_name}",
                    message=f"Required specification '{rule.field}' is missing from drawing.",
                    evidence=(rule_ev,),
                    created_at=now,
                )
                return [finding], [rule_ev]
            return [], []

        # If not REQUIRED and no matching regions found, nothing to violate
        if not matching_regions:
            return [], []

        findings: list[Finding] = []
        evidences: list[Evidence] = []

        for region in matching_regions:
            # Low confidence check -> INSUFFICIENT_INFORMATION
            if region.confidence < 0.6:
                finding = Finding(
                    job_id=job_id,
                    status=FindingStatus.INSUFFICIENT_INFORMATION,
                    severity=rule.severity,
                    confidence=region.confidence,
                    finding_type="low_confidence_region",
                    location=str(region.page_or_sheet),
                    message=(
                        f"Low extraction confidence ({region.confidence:.2f}) on "
                        f"'{region.raw_text}'"
                    ),
                    pixel_bbox=region.pixel_bbox,
                    cad_bbox=region.cad_bbox,
                    created_at=now,
                )
                findings.append(finding)
                continue

            # Evaluate value against operator
            f, evs = self._check_operator(region, rule, doc, job_id)
            if f is not None:
                findings.append(f)
                evidences.extend(evs)

        return findings, evidences

    def _find_matching_regions(self, doc: DrawingDocument, field: str) -> list[TextRegion]:
        f_lower = field.lower()
        matched: list[TextRegion] = []
        for r in doc.regions:
            # Match by layer or text keyword
            layer_match = r.layer is not None and f_lower in r.layer.lower()
            text_match = f_lower in r.raw_text.lower()
            if layer_match or text_match:
                matched.append(r)
            elif f_lower == "tolerance" and any(k in r.raw_text for k in ("+-", "±", "공차")):
                matched.append(r)
            elif f_lower == "material" and any(
                k in r.raw_text for k in ("재질", "SUS", "AL", "SM", "STEEL")
            ):
                matched.append(r)
        return matched

    def _check_operator(
        self,
        region: TextRegion,
        rule: RuleDefinition,
        doc: DrawingDocument,
        job_id: UUID,
    ) -> tuple[Finding | None, list[Evidence]]:
        now = utc_now()
        op = rule.operator

        # Operator: MATCHES (Regex)
        if op == RuleOperator.MATCHES:
            try:
                pattern = re.compile(rule.value)
            except re.error as exc:
                f = Finding(
                    job_id=job_id,
                    status=FindingStatus.INSUFFICIENT_INFORMATION,
                    severity=rule.severity,
                    confidence=1.0,
                    finding_type="invalid_regex_pattern",
                    location=str(region.page_or_sheet),
                    message=f"Invalid regex pattern '{rule.value}': {exc}",
                    created_at=now,
                )
                return f, []

            if not pattern.search(region.raw_text):
                rule_ev = Evidence(kind=EvidenceKind.RULE, ref_id=str(rule.id))
                src_ev = Evidence(
                    kind=EvidenceKind.SOURCE,
                    ref_id=str(doc.drawing_id),
                    location=str(region.page_or_sheet),
                )
                f = Finding(
                    job_id=job_id,
                    status=FindingStatus.VIOLATION,
                    severity=rule.severity,
                    confidence=region.confidence,
                    finding_type="regex_mismatch",
                    location=str(region.page_or_sheet),
                    message=(
                        f"Text '{region.raw_text}' did not match required pattern '{rule.value}'."
                    ),
                    pixel_bbox=region.pixel_bbox,
                    cad_bbox=region.cad_bbox,
                    evidence=(rule_ev, src_ev),
                    created_at=now,
                )
                return f, [rule_ev, src_ev]
            return None, []

        # Operator: EQUALS / ALLOWED_VALUES (String comparison)
        if op == RuleOperator.EQUALS:
            if rule.value.lower() not in region.raw_text.lower():
                rule_ev = Evidence(kind=EvidenceKind.RULE, ref_id=str(rule.id))
                src_ev = Evidence(
                    kind=EvidenceKind.SOURCE,
                    ref_id=str(doc.drawing_id),
                    location=str(region.page_or_sheet),
                )
                f = Finding(
                    job_id=job_id,
                    status=FindingStatus.VIOLATION,
                    severity=rule.severity,
                    confidence=region.confidence,
                    finding_type="value_mismatch",
                    location=str(region.page_or_sheet),
                    message=f"Expected '{rule.value}' for {rule.field}, found '{region.raw_text}'.",
                    pixel_bbox=region.pixel_bbox,
                    cad_bbox=region.cad_bbox,
                    evidence=(rule_ev, src_ev),
                    created_at=now,
                )
                return f, [rule_ev, src_ev]
            return None, []

        if op == RuleOperator.ALLOWED_VALUES:
            allowed = [v.strip().lower() for v in rule.value.split(",") if v.strip()]
            if not any(v in region.raw_text.lower() for v in allowed):
                rule_ev = Evidence(kind=EvidenceKind.RULE, ref_id=str(rule.id))
                src_ev = Evidence(
                    kind=EvidenceKind.SOURCE,
                    ref_id=str(doc.drawing_id),
                    location=str(region.page_or_sheet),
                )
                f = Finding(
                    job_id=job_id,
                    status=FindingStatus.VIOLATION,
                    severity=rule.severity,
                    confidence=region.confidence,
                    finding_type="disallowed_value",
                    location=str(region.page_or_sheet),
                    message=f"Value not in allowed set ({rule.value}): '{region.raw_text}'.",
                    pixel_bbox=region.pixel_bbox,
                    cad_bbox=region.cad_bbox,
                    evidence=(rule_ev, src_ev),
                    created_at=now,
                )
                return f, [rule_ev, src_ev]
            return None, []

        # Numeric operators: MIN, MAX, RANGE
        num_match = NUMERIC_PATTERN.search(region.raw_text)
        if not num_match:
            f = Finding(
                job_id=job_id,
                status=FindingStatus.INSUFFICIENT_INFORMATION,
                severity=rule.severity,
                confidence=region.confidence,
                finding_type="missing_numeric_value",
                location=str(region.page_or_sheet),
                message=f"Cannot extract numeric value from '{region.raw_text}'.",
                created_at=now,
            )
            return f, []

        raw_num = float(num_match.group(1))
        extracted_unit = num_match.group(2) or region.unit or doc.unit

        # Unit verification & conversion
        if not extracted_unit or not rule.unit:
            f = Finding(
                job_id=job_id,
                status=FindingStatus.INSUFFICIENT_INFORMATION,
                severity=rule.severity,
                confidence=region.confidence,
                finding_type="missing_or_unknown_unit",
                location=str(region.page_or_sheet),
                message=f"Missing or unknown unit for numeric comparison in '{region.raw_text}'.",
                created_at=now,
            )
            return f, []

        try:
            converted_val = convert_unit(raw_num, extracted_unit, rule.unit)
        except UnitConversionError as exc:
            f = Finding(
                job_id=job_id,
                status=FindingStatus.INSUFFICIENT_INFORMATION,
                severity=rule.severity,
                confidence=region.confidence,
                finding_type="incompatible_unit",
                location=str(region.page_or_sheet),
                message=f"Unit conversion failed: {exc}",
                created_at=now,
            )
            return f, []

        target_val = float(rule.value)

        # Check MAX
        if op == RuleOperator.MAX and converted_val > target_val:
            rule_ev = Evidence(kind=EvidenceKind.RULE, ref_id=str(rule.id))
            src_ev = Evidence(
                kind=EvidenceKind.SOURCE,
                ref_id=str(doc.drawing_id),
                location=str(region.page_or_sheet),
            )
            f = Finding(
                job_id=job_id,
                status=FindingStatus.VIOLATION,
                severity=rule.severity,
                confidence=region.confidence,
                finding_type="value_exceeds_max",
                location=str(region.page_or_sheet),
                message=(
                    f"{rule.field} value {converted_val} {rule.unit} exceeds "
                    f"max limit of {target_val} {rule.unit}."
                ),
                pixel_bbox=region.pixel_bbox,
                cad_bbox=region.cad_bbox,
                evidence=(rule_ev, src_ev),
                created_at=now,
            )
            return f, [rule_ev, src_ev]

        # Check MIN
        if op == RuleOperator.MIN and converted_val < target_val:
            rule_ev = Evidence(kind=EvidenceKind.RULE, ref_id=str(rule.id))
            src_ev = Evidence(
                kind=EvidenceKind.SOURCE,
                ref_id=str(doc.drawing_id),
                location=str(region.page_or_sheet),
            )
            f = Finding(
                job_id=job_id,
                status=FindingStatus.VIOLATION,
                severity=rule.severity,
                confidence=region.confidence,
                finding_type="value_below_min",
                location=str(region.page_or_sheet),
                message=(
                    f"{rule.field} value {converted_val} {rule.unit} is below "
                    f"min limit of {target_val} {rule.unit}."
                ),
                pixel_bbox=region.pixel_bbox,
                cad_bbox=region.cad_bbox,
                evidence=(rule_ev, src_ev),
                created_at=now,
            )
            return f, [rule_ev, src_ev]

        return None, []
