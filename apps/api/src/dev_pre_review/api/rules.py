"""Rule management endpoints (API-003, API-004)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from dev_pre_review.domain.enums import RuleState
from dev_pre_review.domain.errors import InvalidStateTransition, NotFound, VersionConflict
from dev_pre_review.domain.models import RuleDefinition
from dev_pre_review.main import get_database
from dev_pre_review.rules.catalog import RuleCatalog, RuleValidationError
from dev_pre_review.rules.contracts import RuleCreateRequest, RuleTransitionRequest
from dev_pre_review.storage.database import Database

router = APIRouter(prefix="/api/rules", tags=["rules"])


def get_catalog(db: Annotated[Database, Depends(get_database)]) -> RuleCatalog:
    return RuleCatalog(db.sessions)


@router.get("", response_model=list[RuleDefinition])
def list_rules(
    catalog: Annotated[RuleCatalog, Depends(get_catalog)],
    project_id: Annotated[UUID | None, Query()] = None,
    state: Annotated[RuleState | None, Query()] = None,
) -> list[RuleDefinition]:
    return catalog.list_rules(project_id=project_id, state=state)


@router.post("", response_model=RuleDefinition, status_code=status.HTTP_201_CREATED)
def create_rule(
    req: RuleCreateRequest,
    catalog: Annotated[RuleCatalog, Depends(get_catalog)],
) -> RuleDefinition:
    return catalog.create_rule(req)


@router.post("/{rule_id}/transitions", response_model=RuleDefinition)
def transition_rule(
    rule_id: UUID,
    req: RuleTransitionRequest,
    catalog: Annotated[RuleCatalog, Depends(get_catalog)],
) -> RuleDefinition:

    try:
        return catalog.transition(
            rule_id=rule_id,
            target_state=req.target_state,
            expected_version=req.expected_version,
        )
    except NotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except VersionConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (InvalidStateTransition, RuleValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
