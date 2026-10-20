"""Domain errors. Messages never include drawing content or absolute paths."""

from uuid import UUID


class DomainError(Exception):
    """Base class for expected, user-reportable domain failures."""

    code: str = "domain_error"


class InvalidStateTransition(DomainError):
    code = "invalid_state_transition"

    def __init__(self, entity: str, current: str, action: str) -> None:
        super().__init__(f"{entity} in state '{current}' cannot {action}")
        self.entity = entity
        self.current = current
        self.action = action


class NotFound(DomainError):
    code = "not_found"

    def __init__(self, entity: str, entity_id: UUID) -> None:
        super().__init__(f"{entity} {entity_id} not found")
        self.entity = entity
        self.entity_id = entity_id


class VersionConflict(DomainError):
    code = "version_conflict"

    def __init__(self, entity: str, entity_id: UUID, expected_version: int) -> None:
        super().__init__(f"{entity} {entity_id} changed since version {expected_version}")
        self.entity = entity
        self.entity_id = entity_id
        self.expected_version = expected_version


class ProjectBusy(DomainError):
    code = "project_busy"

    def __init__(self, project_id: UUID) -> None:
        super().__init__(f"project {project_id} has a running analysis")
        self.project_id = project_id


class ProjectDeletionIncomplete(DomainError):
    """Some stores failed to purge; the project stays DELETING and can be resumed."""

    code = "project_deletion_incomplete"

    def __init__(self, project_id: UUID, failed_stores: tuple[str, ...]) -> None:
        super().__init__(f"project {project_id} deletion incomplete: {', '.join(failed_stores)}")
        self.project_id = project_id
        self.failed_stores = failed_stores
