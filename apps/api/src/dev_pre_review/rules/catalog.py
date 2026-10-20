"""RuleCatalog: governed rule state machine, optimistic locking, and audit history."""

from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.engine import CursorResult, RowMapping
from sqlalchemy.orm import Session, sessionmaker

from dev_pre_review.domain.enums import DrawingType, RuleOperator, RuleState, Severity
from dev_pre_review.domain.errors import (
    DomainError,
    InvalidStateTransition,
    NotFound,
    VersionConflict,
)
from dev_pre_review.domain.models import RuleDefinition, utc_now
from dev_pre_review.rules.contracts import RuleCandidate, RuleCreateRequest
from dev_pre_review.storage.schema import rule_history, rules

NUMERIC_FIELDS = frozenset(
    {"tolerance", "dimension", "thickness", "distance", "clearance", "gap", "radius"}
)


class RuleValidationError(DomainError):
    code = "rule_validation_error"


class RuleCatalog:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def add_candidate(self, candidate: RuleCandidate) -> RuleDefinition:
        now = utc_now()
        rule = RuleDefinition(
            id=candidate.id,
            project_id=candidate.project_id,
            state=RuleState.DRAFT,
            drawing_types=candidate.drawing_types,
            field=candidate.field,
            operator=candidate.operator,
            value=candidate.value,
            unit=candidate.unit,
            exceptions=candidate.exceptions,
            severity=candidate.severity,
            source_case_ids=candidate.source_case_ids,
            version=1,
        )

        with self.session_factory() as session, session.begin():
            session.execute(
                insert(rules).values(
                    id=rule.id,
                    project_id=rule.project_id,
                    state=rule.state.value,
                    drawing_types=[dt.value for dt in rule.drawing_types],
                    field=rule.field,
                    operator=rule.operator.value,
                    value=rule.value,
                    unit=rule.unit,
                    exceptions=list(rule.exceptions),
                    severity=rule.severity.value,
                    source_case_ids=[str(cid) for cid in rule.source_case_ids],
                    version=rule.version,
                    created_at=now,
                    updated_at=now,
                )
            )

        return rule

    def create_rule(self, req: RuleCreateRequest) -> RuleDefinition:
        candidate = RuleCandidate(
            id=uuid4(),
            project_id=req.project_id,
            drawing_types=tuple(req.drawing_types),
            field=req.field,
            operator=req.operator,
            value=req.value,
            unit=req.unit,
            exceptions=tuple(req.exceptions),
            severity=req.severity,
            source_case_ids=tuple(req.source_case_ids),
        )
        return self.add_candidate(candidate)

    def get(self, rule_id: UUID) -> RuleDefinition:
        with self.session_factory() as session:
            row = (
                session.execute(select(rules).where(rules.c.id == rule_id)).mappings().one_or_none()
            )
            if row is None:
                raise NotFound("RuleDefinition", rule_id)
            return self._row_to_model(row)

    def transition(
        self, rule_id: UUID, target_state: RuleState, expected_version: int
    ) -> RuleDefinition:
        with self.session_factory() as session, session.begin():
            row = (
                session.execute(select(rules).where(rules.c.id == rule_id)).mappings().one_or_none()
            )
            if row is None:
                raise NotFound("RuleDefinition", rule_id)

            current_rule = self._row_to_model(row)

            # Optimistic concurrency check
            if current_rule.version != expected_version:
                raise VersionConflict("RuleDefinition", rule_id, expected_version)

            current_state = current_rule.state

            # State transition validation (RULE-002, RULE-005)
            if current_state == RuleState.INACTIVE:
                raise InvalidStateTransition(
                    "RuleDefinition", "inactive", f"transition to {target_state}"
                )
            if current_state == RuleState.APPROVED and target_state != RuleState.INACTIVE:
                raise InvalidStateTransition(
                    "RuleDefinition", "approved", f"transition to {target_state}"
                )
            if current_state == RuleState.DRAFT and target_state not in (
                RuleState.APPROVED,
                RuleState.INACTIVE,
            ):
                raise InvalidStateTransition(
                    "RuleDefinition", "draft", f"transition to {target_state}"
                )

            # Specific approval validation
            if target_state == RuleState.APPROVED:
                self._validate_for_approval(current_rule)

            new_version = current_rule.version + 1
            now = utc_now()

            result = cast(
                CursorResult[Any],
                session.execute(
                    update(rules)
                    .where(rules.c.id == rule_id, rules.c.version == expected_version)
                    .values(
                        state=target_state.value,
                        version=new_version,
                        updated_at=now,
                    )
                ),
            )
            if result.rowcount == 0:
                raise VersionConflict("RuleDefinition", rule_id, expected_version)

            # Record transition in rule_history
            session.execute(
                insert(rule_history).values(
                    rule_id=rule_id,
                    from_state=current_state.value,
                    to_state=target_state.value,
                    version=new_version,
                    created_at=now,
                )
            )

        return current_rule.model_copy(update={"state": target_state, "version": new_version})

    def list_rules(
        self, project_id: UUID | None = None, state: RuleState | None = None
    ) -> list[RuleDefinition]:
        query = select(rules)
        if project_id is not None:
            query = query.where(rules.c.project_id == project_id)
        if state is not None:
            query = query.where(rules.c.state == state.value)
        query = query.order_by(rules.c.created_at.asc())

        with self.session_factory() as session:
            rows = session.execute(query).mappings().all()
            return [self._row_to_model(r) for r in rows]

    def _validate_for_approval(self, rule: RuleDefinition) -> None:
        # Check source cases requirement
        if not rule.source_case_ids:
            raise RuleValidationError("source required for approved rule")

        # Check numeric unit requirement
        is_numeric = rule.field.lower() in NUMERIC_FIELDS
        if not is_numeric:
            try:
                float(rule.value)
                is_numeric = True
            except ValueError:
                pass

        if is_numeric and not rule.unit:
            raise RuleValidationError("unit required for numeric rule")

    @staticmethod
    def _row_to_model(row: RowMapping) -> RuleDefinition:
        d_types = tuple(DrawingType(dt) for dt in cast(list[str], row["drawing_types"]))
        c_ids = tuple(UUID(cid) for cid in cast(list[str], row["source_case_ids"]))
        return RuleDefinition(
            id=row["id"],
            project_id=row["project_id"],
            state=RuleState(str(row["state"])),
            drawing_types=d_types,
            field=str(row["field"]),
            operator=RuleOperator(str(row["operator"])),
            value=str(row["value"]),
            unit=cast(str | None, row["unit"]),
            exceptions=tuple(cast(list[str], row["exceptions"])),
            severity=Severity(str(row["severity"])),
            source_case_ids=c_ids,
            version=row["version"],
        )
