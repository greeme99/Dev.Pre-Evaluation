"""Enumerations shared across the domain, persisted by value."""

from enum import StrEnum


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    DELETING = "deleting"


class JobState(StrEnum):
    """FN-007 job states."""

    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    FAILED = "failed"
    COMPLETED = "completed"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_JOB_STATES


TERMINAL_JOB_STATES = frozenset({JobState.CANCELLED, JobState.FAILED, JobState.COMPLETED})


class AnalysisStep(StrEnum):
    """FN-007 pipeline steps. Declaration order is the execution order."""

    VALIDATE = "validate"
    EXTRACT = "extract"
    RULES = "rules"
    RETRIEVE = "retrieve"
    SUGGEST = "suggest"
    EXPORT_READY = "export_ready"


ANALYSIS_STEPS: tuple[AnalysisStep, ...] = tuple(AnalysisStep)


class FindingStatus(StrEnum):
    """Verdicts: only approved rules may produce VIOLATION."""

    VIOLATION = "violation"
    SUSPECTED = "suspected"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RuleState(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    INACTIVE = "inactive"


class RuleOperator(StrEnum):
    """The seven MVP operators (plan.md Task 8)."""

    REQUIRED = "required"
    EQUALS = "equals"
    MATCHES = "matches"
    MIN = "min"
    MAX = "max"
    RANGE = "range"
    ALLOWED_VALUES = "allowed_values"


class DrawingType(StrEnum):
    PDF = "pdf"
    DXF = "dxf"


class EvidenceKind(StrEnum):
    RULE = "rule"
    CASE = "case"
    SOURCE = "source"
