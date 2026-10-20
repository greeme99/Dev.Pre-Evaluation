"""Repository implementations for SQLite schema."""

from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import CursorResult, RowMapping
from sqlalchemy.orm import Session, sessionmaker

from dev_pre_review.domain.enums import (
    AnalysisStep,
    DrawingType,
    EvidenceKind,
    FindingStatus,
    JobState,
    ProjectStatus,
    Severity,
)
from dev_pre_review.domain.errors import NotFound, VersionConflict
from dev_pre_review.domain.models import (
    AnalysisJob,
    DrawingArtifact,
    Evidence,
    Finding,
    ReviewProject,
)
from dev_pre_review.storage.schema import (
    analysis_jobs,
    drawing_artifacts,
    evidence,
    findings,
    projects,
)


class ProjectRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def add(self, project: ReviewProject) -> ReviewProject:
        with self.session_factory() as session, session.begin():
            session.execute(
                insert(projects).values(
                    id=project.id,
                    name=project.name,
                    status=project.status.value,
                    created_at=project.created_at,
                    data_version=project.data_version,
                )
            )
        return project

    def get(self, project_id: UUID) -> ReviewProject:
        with self.session_factory() as session:
            row = (
                session.execute(select(projects).where(projects.c.id == project_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise NotFound("ReviewProject", project_id)
            return ReviewProject(
                id=row["id"],
                name=row["name"],
                status=ProjectStatus(row["status"]),
                created_at=row["created_at"],
                data_version=row["data_version"],
            )

    def update(self, project: ReviewProject) -> ReviewProject:
        with self.session_factory() as session, session.begin():
            result = cast(
                CursorResult[Any],
                session.execute(
                    update(projects)
                    .where(projects.c.id == project.id)
                    .values(
                        name=project.name,
                        status=project.status.value,
                        data_version=project.data_version + 1,
                    )
                ),
            )
            if result.rowcount == 0:
                raise NotFound("ReviewProject", project.id)
        return project.model_copy(update={"data_version": project.data_version + 1})

    def delete(self, project_id: UUID) -> None:
        with self.session_factory() as session, session.begin():
            session.execute(delete(projects).where(projects.c.id == project_id))

    def list_by_status(self, status: ProjectStatus) -> list[ReviewProject]:
        with self.session_factory() as session:
            rows = (
                session.execute(select(projects).where(projects.c.status == status.value))
                .mappings()
                .all()
            )
            return [
                ReviewProject(
                    id=row["id"],
                    name=row["name"],
                    status=ProjectStatus(row["status"]),
                    created_at=row["created_at"],
                    data_version=row["data_version"],
                )
                for row in rows
            ]


class DrawingRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def add(self, drawing: DrawingArtifact) -> DrawingArtifact:
        with self.session_factory() as session, session.begin():
            session.execute(
                insert(drawing_artifacts).values(
                    id=drawing.id,
                    project_id=drawing.project_id,
                    sha256=drawing.sha256,
                    drawing_type=drawing.drawing_type.value,
                    source_name=drawing.source_name,
                    parser_version=drawing.parser_version,
                    created_at=drawing.created_at,
                )
            )
        return drawing

    def get(self, drawing_id: UUID) -> DrawingArtifact:
        with self.session_factory() as session:
            row = (
                session.execute(
                    select(drawing_artifacts).where(drawing_artifacts.c.id == drawing_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise NotFound("DrawingArtifact", drawing_id)
            return DrawingArtifact(
                id=row["id"],
                project_id=row["project_id"],
                sha256=row["sha256"],
                drawing_type=DrawingType(row["drawing_type"]),
                source_name=row["source_name"],
                parser_version=row["parser_version"],
                created_at=row["created_at"],
            )


class JobRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def add(self, job: AnalysisJob) -> AnalysisJob:
        with self.session_factory() as session, session.begin():
            max_seq = session.execute(select(func.max(analysis_jobs.c.seq))).scalar()
            seq = 1 if max_seq is None else max_seq + 1
            session.execute(
                insert(analysis_jobs).values(
                    id=job.id,
                    seq=seq,
                    project_id=job.project_id,
                    drawing_id=job.drawing_id,
                    state=job.state.value,
                    completed_steps=[step.value for step in job.completed_steps],
                    failed_step=job.failed_step.value if job.failed_step else None,
                    error_code=job.error_code,
                    config_versions=job.config_versions,
                    created_at=job.created_at,
                    started_at=job.started_at,
                    finished_at=job.finished_at,
                    updated_at=job.updated_at,
                    version=job.version,
                )
            )
        return job

    def get(self, job_id: UUID) -> AnalysisJob:
        with self.session_factory() as session:
            row = (
                session.execute(select(analysis_jobs).where(analysis_jobs.c.id == job_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise NotFound("AnalysisJob", job_id)
            return self._row_to_model(row)

    def update(self, job: AnalysisJob) -> AnalysisJob:
        new_version = job.version + 1
        with self.session_factory() as session, session.begin():
            result = cast(
                CursorResult[Any],
                session.execute(
                    update(analysis_jobs)
                    .where(analysis_jobs.c.id == job.id, analysis_jobs.c.version == job.version)
                    .values(
                        state=job.state.value,
                        completed_steps=[step.value for step in job.completed_steps],
                        failed_step=job.failed_step.value if job.failed_step else None,
                        error_code=job.error_code,
                        config_versions=job.config_versions,
                        started_at=job.started_at,
                        finished_at=job.finished_at,
                        updated_at=job.updated_at,
                        version=new_version,
                    )
                ),
            )
            if result.rowcount == 0:
                raise VersionConflict("AnalysisJob", job.id, job.version)
        return job.model_copy(update={"version": new_version})

    def count_running(self) -> int:
        with self.session_factory() as session:
            count = session.execute(
                select(func.count())
                .select_from(analysis_jobs)
                .where(
                    analysis_jobs.c.state.in_([JobState.RUNNING.value, JobState.CANCELLING.value])
                )
            ).scalar_one()
            return int(count)

    def count_running_for_project(self, project_id: UUID) -> int:
        with self.session_factory() as session:
            count = session.execute(
                select(func.count())
                .select_from(analysis_jobs)
                .where(
                    analysis_jobs.c.project_id == project_id,
                    analysis_jobs.c.state.in_([JobState.RUNNING.value, JobState.CANCELLING.value]),
                )
            ).scalar_one()
            return int(count)

    def claim_next(self) -> AnalysisJob | None:
        """Atomically claim the oldest queued job if no other job is running."""
        with self.session_factory() as session, session.begin():
            running = session.execute(
                select(func.count())
                .select_from(analysis_jobs)
                .where(
                    analysis_jobs.c.state.in_([JobState.RUNNING.value, JobState.CANCELLING.value])
                )
            ).scalar_one()
            if running > 0:
                return None

            row = (
                session.execute(
                    select(analysis_jobs)
                    .where(analysis_jobs.c.state == JobState.QUEUED.value)
                    .order_by(analysis_jobs.c.seq.asc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None

            job = self._row_to_model(row).start()
            new_version = job.version + 1
            session.execute(
                update(analysis_jobs)
                .where(analysis_jobs.c.id == job.id, analysis_jobs.c.version == row["version"])
                .values(
                    state=job.state.value,
                    started_at=job.started_at,
                    updated_at=job.updated_at,
                    version=new_version,
                )
            )
            return job.model_copy(update={"version": new_version})

    def list_interrupted(self) -> list[AnalysisJob]:
        with self.session_factory() as session:
            rows = (
                session.execute(
                    select(analysis_jobs)
                    .where(
                        analysis_jobs.c.state.in_(
                            [JobState.RUNNING.value, JobState.CANCELLING.value]
                        )
                    )
                    .order_by(analysis_jobs.c.seq.asc())
                )
                .mappings()
                .all()
            )
            return [self._row_to_model(row) for row in rows]

    def cancel_queued_for_project(self, project_id: UUID) -> None:
        with self.session_factory() as session, session.begin():
            rows = (
                session.execute(
                    select(analysis_jobs).where(
                        analysis_jobs.c.project_id == project_id,
                        analysis_jobs.c.state == JobState.QUEUED.value,
                    )
                )
                .mappings()
                .all()
            )
            for r in rows:
                session.execute(
                    update(analysis_jobs)
                    .where(analysis_jobs.c.id == r["id"])
                    .values(
                        state=JobState.CANCELLED.value,
                        version=r["version"] + 1,
                    )
                )

    @staticmethod
    def _row_to_model(row: RowMapping) -> AnalysisJob:
        completed = tuple(AnalysisStep(s) for s in cast(list[str], row["completed_steps"]))
        failed = AnalysisStep(str(row["failed_step"])) if row["failed_step"] else None
        return AnalysisJob(
            id=row["id"],
            project_id=row["project_id"],
            drawing_id=row["drawing_id"],
            state=JobState(str(row["state"])),
            completed_steps=completed,
            failed_step=failed,
            error_code=cast(str | None, row["error_code"]),
            config_versions=cast(dict[str, str], row["config_versions"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            updated_at=row["updated_at"],
            version=row["version"],
        )


class FindingRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def add_many(self, finding_list: list[Finding]) -> None:
        with self.session_factory() as session, session.begin():
            for f in finding_list:
                session.execute(
                    insert(findings).values(
                        id=f.id,
                        job_id=f.job_id,
                        status=f.status.value,
                        severity=f.severity.value,
                        confidence=f.confidence,
                        finding_type=f.finding_type,
                        location=f.location,
                        message=f.message,
                        pixel_bbox=list(f.pixel_bbox) if f.pixel_bbox else None,
                        cad_bbox=list(f.cad_bbox) if f.cad_bbox else None,
                        created_at=f.created_at,
                    )
                )
                for idx, ev in enumerate(f.evidence):
                    session.execute(
                        insert(evidence).values(
                            finding_id=f.id,
                            position=idx,
                            kind=ev.kind.value,
                            ref_id=ev.ref_id,
                            score=ev.score,
                            location=ev.location,
                        )
                    )

    def list_for_job(self, job_id: UUID) -> list[Finding]:
        with self.session_factory() as session:
            f_rows = (
                session.execute(
                    select(findings)
                    .where(findings.c.job_id == job_id)
                    .order_by(findings.c.created_at.asc())
                )
                .mappings()
                .all()
            )

            results: list[Finding] = []
            for f_row in f_rows:
                ev_rows = (
                    session.execute(
                        select(evidence)
                        .where(evidence.c.finding_id == f_row["id"])
                        .order_by(evidence.c.position.asc())
                    )
                    .mappings()
                    .all()
                )
                ev_list = tuple(
                    Evidence(
                        kind=EvidenceKind(e["kind"]),
                        ref_id=e["ref_id"],
                        score=e["score"],
                        location=e["location"],
                    )
                    for e in ev_rows
                )
                p_bbox = (
                    cast(tuple[float, float, float, float], tuple(f_row["pixel_bbox"]))
                    if f_row["pixel_bbox"]
                    else None
                )
                c_bbox = (
                    cast(tuple[float, float, float, float], tuple(f_row["cad_bbox"]))
                    if f_row["cad_bbox"]
                    else None
                )
                results.append(
                    Finding(
                        id=f_row["id"],
                        job_id=f_row["job_id"],
                        status=FindingStatus(f_row["status"]),
                        severity=Severity(f_row["severity"]),
                        confidence=f_row["confidence"],
                        finding_type=f_row["finding_type"],
                        location=f_row["location"],
                        message=f_row["message"],
                        pixel_bbox=p_bbox,
                        cad_bbox=c_bbox,
                        evidence=ev_list,
                        created_at=f_row["created_at"],
                    )
                )
            return results
