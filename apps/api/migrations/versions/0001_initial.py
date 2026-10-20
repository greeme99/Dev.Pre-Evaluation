"""Initial schema: projects, drawing_artifacts, analysis_jobs, findings, evidence.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("data_version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )

    op.create_table(
        "drawing_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("drawing_type", sa.String(length=8), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_drawing_artifacts_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_drawing_artifacts")),
    )
    op.create_index(
        op.f("ix_drawing_artifacts_project_id"),
        "drawing_artifacts",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("drawing_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("completed_steps", sa.JSON(), nullable=False),
        sa.Column("failed_step", sa.String(length=32), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("config_versions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["drawing_id"],
            ["drawing_artifacts.id"],
            name=op.f("fk_analysis_jobs_drawing_id_drawing_artifacts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_analysis_jobs_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_jobs")),
        sa.UniqueConstraint("seq", name=op.f("uq_analysis_jobs_seq")),
    )
    op.create_index(
        op.f("ix_analysis_jobs_drawing_id"),
        "analysis_jobs",
        ["drawing_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_jobs_project_id"),
        "analysis_jobs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_jobs_state_seq",
        "analysis_jobs",
        ["state", "seq"],
        unique=False,
    )

    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=8), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("finding_type", sa.String(length=64), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("pixel_bbox", sa.JSON(), nullable=True),
        sa.Column("cad_bbox", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["analysis_jobs.id"],
            name=op.f("fk_findings_job_id_analysis_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_findings")),
    )
    op.create_index(op.f("ix_findings_job_id"), "findings", ["job_id"], unique=False)

    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("ref_id", sa.String(length=128), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            name=op.f("fk_evidence_finding_id_findings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence")),
    )
    op.create_index(op.f("ix_evidence_finding_id"), "evidence", ["finding_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_evidence_finding_id"), table_name="evidence")
    op.drop_table("evidence")
    op.drop_index(op.f("ix_findings_job_id"), table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_analysis_jobs_state_seq", table_name="analysis_jobs")
    op.drop_index(op.f("ix_analysis_jobs_project_id"), table_name="analysis_jobs")
    op.drop_index(op.f("ix_analysis_jobs_drawing_id"), table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
    op.drop_index(op.f("ix_drawing_artifacts_project_id"), table_name="drawing_artifacts")
    op.drop_table("drawing_artifacts")
    op.drop_table("projects")
