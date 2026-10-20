"""Project cascade deletion service and external store purgers (FR-016, RULE-008, TC-031)."""

import shutil
from pathlib import Path
from typing import Protocol
from uuid import UUID

from dev_pre_review.domain.enums import ProjectStatus
from dev_pre_review.domain.errors import NotFound, ProjectBusy, ProjectDeletionIncomplete
from dev_pre_review.storage.repositories import JobRepository, ProjectRepository


class ExternalStorePurger(Protocol):
    name: str

    def purge_project(self, project_id: UUID) -> None: ...


class FileStorePurger:
    name = "file-store"

    def __init__(self, root: Path) -> None:
        self.root = root

    def purge_project(self, project_id: UUID) -> None:
        p_dir = self.root / "projects" / str(project_id)
        if p_dir.exists():
            shutil.rmtree(p_dir)


class ProjectDeletionService:
    def __init__(
        self,
        projects: ProjectRepository,
        jobs: JobRepository,
        purgers: list[ExternalStorePurger] | None = None,
    ) -> None:
        self.projects = projects
        self.jobs = jobs
        self.purgers = purgers or []

    def delete(self, project_id: UUID) -> None:
        try:
            project = self.projects.get(project_id)
        except NotFound:
            return

        if self.jobs.count_running_for_project(project_id) > 0:
            raise ProjectBusy(project_id)

        if project.status is not ProjectStatus.DELETING:
            self.projects.update(project.model_copy(update={"status": ProjectStatus.DELETING}))

        self.jobs.cancel_queued_for_project(project_id)

        failed_stores: list[str] = []
        for purger in self.purgers:
            try:
                purger.purge_project(project_id)
            except Exception:  # noqa: BLE001
                failed_stores.append(purger.name)

        if failed_stores:
            raise ProjectDeletionIncomplete(project_id, tuple(failed_stores))

        self.projects.delete(project_id)

    def resume_pending(self) -> list[UUID]:
        deleting_projects = self.projects.list_by_status(ProjectStatus.DELETING)
        resumed: list[UUID] = []
        for p in deleting_projects:
            self.delete(p.id)
            resumed.append(p.id)
        return resumed
