"""Alembic migrations stay in sync with the SQLAlchemy schema."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from dev_pre_review.storage.database import Database
from dev_pre_review.storage.schema import metadata

EXPECTED_TABLES = {"projects", "drawing_artifacts", "analysis_jobs", "findings", "evidence"}


def test_upgrade_head_creates_expected_tables(database: Database) -> None:
    tables = set(inspect(database.engine).get_table_names())
    assert EXPECTED_TABLES <= tables


def test_migration_matches_schema_metadata(database: Database) -> None:
    with database.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        diff = compare_metadata(context, metadata)
    assert diff == []


def test_upgrade_is_idempotent(database: Database) -> None:
    database.upgrade()


def test_foreign_keys_are_enforced(database: Database) -> None:
    with pytest.raises(IntegrityError), database.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO drawing_artifacts "
                "(id, project_id, sha256, drawing_type, source_name, parser_version, created_at) "
                "VALUES ('a', 'missing', :sha, 'pdf', 'x.pdf', 'v', '2026-01-01 00:00:00')"
            ),
            {"sha": "0" * 64},
        )
