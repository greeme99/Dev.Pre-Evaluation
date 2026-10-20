"""Deterministic rule candidate extractor for structured patterns."""

import re

from dev_pre_review.domain.enums import DrawingType, RuleOperator, Severity
from dev_pre_review.domain.models import KnowledgeCase
from dev_pre_review.rules.contracts import RuleCandidate

TOLERANCE_PATTERN = re.compile(
    r"(?:공차|tolerance)[^\d]*?(?:[±\+\-]+\s*)?(\d+(?:\.\d+)?)\s*(mm|um|µm)?",
    re.IGNORECASE,
)
MATERIAL_PATTERN = re.compile(
    r"(?:재질|material)[^\w]*(SUS\d+|AL\d+|SS\d+|SM\d+|S\d+C|SKD\d+)",
    re.IGNORECASE,
)
LAYER_PATTERN = re.compile(
    r"(?:레이어|layer)[^\w]*([A-Z0-9_\-]+)",
    re.IGNORECASE,
)


class RuleCandidateExtractor:
    def extract(self, case: KnowledgeCase) -> list[RuleCandidate]:
        candidates: list[RuleCandidate] = []
        text = case.text

        # 1. Tolerance pattern
        tol_match = TOLERANCE_PATTERN.search(text)
        if tol_match:
            val = tol_match.group(1)
            unit = tol_match.group(2) or "mm"
            candidates.append(
                RuleCandidate(
                    project_id=case.project_id,
                    drawing_types=(DrawingType.PDF, DrawingType.DXF),
                    field="tolerance",
                    operator=RuleOperator.MAX,
                    value=val,
                    unit=unit,
                    severity=Severity.HIGH,
                    source_case_ids=(case.id,),
                )
            )

        # 2. Material pattern
        mat_match = MATERIAL_PATTERN.search(text)
        if mat_match:
            val = mat_match.group(1).upper()
            candidates.append(
                RuleCandidate(
                    project_id=case.project_id,
                    drawing_types=(DrawingType.PDF, DrawingType.DXF),
                    field="material",
                    operator=RuleOperator.EQUALS,
                    value=val,
                    unit=None,
                    severity=Severity.HIGH,
                    source_case_ids=(case.id,),
                )
            )

        # 3. Layer pattern
        layer_match = LAYER_PATTERN.search(text)
        if layer_match and not mat_match:  # avoid collision if layer pattern matches material
            val = layer_match.group(1).upper()
            candidates.append(
                RuleCandidate(
                    project_id=case.project_id,
                    drawing_types=(DrawingType.DXF,),
                    field="layer",
                    operator=RuleOperator.EQUALS,
                    value=val,
                    unit=None,
                    severity=Severity.MEDIUM,
                    source_case_ids=(case.id,),
                )
            )

        return candidates
