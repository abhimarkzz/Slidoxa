"""Normalized Blackboard schema and slide OCC integration tests.

SLIDOXA_PG_TEST_URL must reference a disposable test database only. These
fixtures reset the schema using Alembic; never point the variable at live DB.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

PG_URL = os.getenv("SLIDOXA_PG_TEST_URL")
ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"
pytestmark = pytest.mark.skipif(not PG_URL, reason="SLIDOXA_PG_TEST_URL not set")
EXPECTED_TABLES = {
    "workspaces", "users", "provider_keys", "presentations",
    "source_documents", "document_chunks", "evidence_facts", "slides",
    "qa_findings", "job_queue", "deck_events", "agent_runs",
}


@pytest.fixture(scope="module", autouse=True)
def _fresh_disposable_database():
    assert PG_URL
    env = {**os.environ, "DATABASE_URL": PG_URL}
    subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI), "downgrade", "base"],
        env=env,
        check=True,
    )
    subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
        env=env,
        check=True,
    )
    yield


def _engine() -> sa.Engine:
    assert PG_URL
    return sa.create_engine(PG_URL, future=True)


def test_exactly_twelve_application_tables_and_expected_foreign_keys():
    with _engine().connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                sa.text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE' "
                    "AND table_name <> 'alembic_version'"
                )
            )
        }
        assert tables == EXPECTED_TABLES

        foreign_keys = {
            (row[0], row[1], row[2])
            for row in connection.execute(
                sa.text(
                    "SELECT tc.table_name, kcu.column_name, ccu.table_name "
                    "FROM information_schema.table_constraints tc "
                    "JOIN information_schema.key_column_usage kcu "
                    "ON tc.constraint_name=kcu.constraint_name "
                    "AND tc.constraint_schema=kcu.constraint_schema "
                    "JOIN information_schema.constraint_column_usage ccu "
                    "ON ccu.constraint_name=tc.constraint_name "
                    "AND ccu.constraint_schema=tc.constraint_schema "
                    "WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public'"
                )
            )
        }
        assert ("users", "workspace_id", "workspaces") in foreign_keys
        assert ("provider_keys", "user_id", "users") in foreign_keys
        assert ("slides", "presentation_id", "presentations") in foreign_keys
        assert ("deck_events", "slide_id", "slides") in foreign_keys
        assert ("agent_runs", "job_id", "job_queue") in foreign_keys
        assert len(foreign_keys) == 23


def test_slide_occ_increments_version_and_rejects_stale_write():
    from app.api.blackboard_ops import StaleSlideVersion, update_slide_optimistically
    from app.api.models import Presentation, Slide, Workspace

    workspace_id = uuid.uuid4()
    presentation_id = uuid.uuid4()
    slide_id = uuid.uuid4()

    with Session(_engine()) as session:
        session.add(Workspace(workspace_id=workspace_id, name="OCC integration test"))
        session.flush()
        session.add(
            Presentation(
                presentation_id=presentation_id,
                workspace_id=workspace_id,
                title="OCC test",
            )
        )
        session.flush()
        session.add(
            Slide(
                slide_id=slide_id,
                presentation_id=presentation_id,
                slide_number=1,
                layout_type="title",
                ast_json={"text": "before"},
                version=1,
            )
        )
        session.commit()

        new_version, event_id = update_slide_optimistically(
            session,
            slide_id=slide_id,
            expected_version=1,
            ast_json={"text": "after"},
        )
        assert new_version == 2
        session.commit()

        with pytest.raises(StaleSlideVersion) as exc_info:
            update_slide_optimistically(
                session,
                slide_id=slide_id,
                expected_version=1,
                ast_json={"text": "stale overwrite"},
            )
        assert exc_info.value.latest_version == 2

        persisted_version = session.execute(
            sa.text("SELECT version FROM slides WHERE slide_id=:slide_id"),
            {"slide_id": slide_id},
        ).scalar_one()
        assert persisted_version == 2
        persisted_event_count = session.execute(
            sa.text("SELECT count(*) FROM deck_events WHERE event_id=:event_id"),
            {"event_id": event_id},
        ).scalar_one()
        assert persisted_event_count == 1
        session.rollback()
