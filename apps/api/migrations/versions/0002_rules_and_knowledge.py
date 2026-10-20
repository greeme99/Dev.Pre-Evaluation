"""Add knowledge_cases, rules, rule_history, and import_records.

Revision ID: 0002_rules_and_knowledge
Revises: 0001_initial
Create Date: 2026-10-20 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_rules_and_knowledge"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("table_data", sa.JSON(), nullable=False),
        sa.Column("image_refs", sa.JSON(), nullable=False),
        sa.Column("source_file_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_sheet", sa.String(length=128), nullable=False),
        sa.Column("source_cell", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_knowledge_cases_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_cases")),
    )
    op.create_index(
        op.f("ix_knowledge_cases_project_id"),
        "knowledge_cases",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("drawing_types", sa.JSON(), nullable=False),
        sa.Column("field", sa.String(length=64), nullable=False),
        sa.Column("operator", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=True),
        sa.Column("exceptions", sa.JSON(), nullable=False),
        sa.Column("severity", sa.String(length=8), nullable=False),
        sa.Column("source_case_ids", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_rules_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rules")),
    )
    op.create_index(op.f("ix_rules_project_id"), "rules", ["project_id"], unique=False)

    op.create_table(
        "rule_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("from_state", sa.String(length=16), nullable=False),
        sa.Column("to_state", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["rules.id"],
            name=op.f("fk_rule_history_rule_id_rules"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rule_history")),
    )
    op.create_index(op.f("ix_rule_history_rule_id"), "rule_history", ["rule_id"], unique=False)

    op.create_table(
        "import_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("sheet_name", sa.String(length=128), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_import_records_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_records")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_import_records_idempotency_key")),
    )
    op.create_index(
        op.f("ix_import_records_file_sha256"),
        "import_records",
        ["file_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_import_records_project_id"),
        "import_records",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_import_records_project_id"), table_name="import_records")
    op.drop_index(op.f("ix_import_records_file_sha256"), table_name="import_records")
    op.drop_table("import_records")
    op.drop_index(op.f("ix_rule_history_rule_id"), table_name="rule_history")
    op.drop_table("rule_history")
    op.drop_index(op.f("ix_rules_project_id"), table_name="rules")
    op.drop_table("rules")
    op.drop_index(op.f("ix_knowledge_cases_project_id"), table_name="knowledge_cases")
    op.drop_table("knowledge_cases")
