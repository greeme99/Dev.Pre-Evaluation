"""SQLAlchemy Core schema. Alembic migrations must mirror this exactly (drift-tested)."""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Dialect,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    TypeDecorator,
    Uuid,
)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UTCDateTime(TypeDecorator[datetime]):
    """Stores naive UTC in SQLite; always returns timezone-aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime is not allowed; use UTC-aware values")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


def _fk(target: str) -> ForeignKey:
    return ForeignKey(target, ondelete="CASCADE")


projects = Table(
    "projects",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", String(200), nullable=False),
    Column("status", String(16), nullable=False),
    Column("created_at", UTCDateTime, nullable=False),
    Column("data_version", Integer, nullable=False),
)

drawing_artifacts = Table(
    "drawing_artifacts",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("project_id", Uuid, _fk("projects.id"), nullable=False, index=True),
    Column("sha256", String(64), nullable=False),
    Column("drawing_type", String(8), nullable=False),
    Column("source_name", String(255), nullable=False),
    Column("parser_version", String(64), nullable=False),
    Column("created_at", UTCDateTime, nullable=False),
)

analysis_jobs = Table(
    "analysis_jobs",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("seq", Integer, nullable=False, unique=True),
    Column("project_id", Uuid, _fk("projects.id"), nullable=False, index=True),
    Column("drawing_id", Uuid, _fk("drawing_artifacts.id"), nullable=False, index=True),
    Column("state", String(16), nullable=False),
    Column("completed_steps", JSON, nullable=False),
    Column("failed_step", String(32), nullable=True),
    Column("error_code", String(64), nullable=True),
    Column("config_versions", JSON, nullable=False),
    Column("created_at", UTCDateTime, nullable=False),
    Column("started_at", UTCDateTime, nullable=True),
    Column("finished_at", UTCDateTime, nullable=True),
    Column("updated_at", UTCDateTime, nullable=False),
    Column("version", Integer, nullable=False),
    Index("ix_analysis_jobs_state_seq", "state", "seq"),
)

findings = Table(
    "findings",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("job_id", Uuid, _fk("analysis_jobs.id"), nullable=False, index=True),
    Column("status", String(32), nullable=False),
    Column("severity", String(8), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("finding_type", String(64), nullable=False),
    Column("location", String(255), nullable=False),
    Column("message", Text, nullable=False),
    Column("pixel_bbox", JSON, nullable=True),
    Column("cad_bbox", JSON, nullable=True),
    Column("created_at", UTCDateTime, nullable=False),
)

evidence = Table(
    "evidence",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("finding_id", Uuid, _fk("findings.id"), nullable=False, index=True),
    Column("position", Integer, nullable=False),
    Column("kind", String(16), nullable=False),
    Column("ref_id", String(128), nullable=False),
    Column("score", Float, nullable=True),
    Column("location", String(255), nullable=True),
)
