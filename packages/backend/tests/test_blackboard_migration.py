"""Alembic upgrade/downgrade/re-upgrade against a disposable pgvector DB.

Skipped automatically when ``SLIDOXA_PG_TEST_URL`` is not set so this
test can live in the suite without forcing every contributor to have
Docker running. The CI workflow is expected to start pgvector/pgvector:pg16,
set SLIDOXA_PG_TEST_URL, and then invoke pytest.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"

PG_URL = os.getenv("SLIDOXA_PG_TEST_URL")
pytestmark = pytest.mark.skipif(
    not PG_URL, reason="SLIDOXA_PG_TEST_URL not set; skipping live-pg migration test"
)


def _alembic(cmd: list[str], env: dict) -> subprocess.CompletedProcess:
    # Explicitly no shell=True.
    return subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI), *cmd],
        env={**os.environ, **env, "DATABASE_URL": PG_URL or ""},
        capture_output=True,
        check=True,
        text=True,
    )


def _engine() -> sa.Engine:
    assert PG_URL
    return sa.create_engine(PG_URL, future=True)


def test_upgrade_creates_table_and_vector_extension(monkeypatch):
    _alembic(["upgrade", "head"], {})
    with _engine().connect() as c:
        ext = c.execute(
            sa.text("SELECT extname FROM pg_extension WHERE extname='vector'")
        ).scalar()
        assert ext == "vector"
        tables = c.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='blackboard_entry'"
            )
        ).scalar()
        assert tables == "blackboard_entry"
        indexes = {
            row[0]
            for row in c.execute(
                sa.text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename='blackboard_entry'"
                )
            )
        }
        assert {
            "blackboard_entry_pkey",
            "blackboard_entry_owner_live_idx",
            "blackboard_entry_owner_kind_live_idx",
            "blackboard_entry_embedding_hnsw_idx",
        }.issubset(indexes)


def test_downgrade_removes_only_this_migrations_objects(monkeypatch):
    _alembic(["downgrade", "base"], {})
    with _engine().connect() as c:
        remaining = c.execute(
            sa.text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='blackboard_entry'"
            )
        ).scalar()
        assert remaining == 0
        ext = c.execute(
            sa.text("SELECT extname FROM pg_extension WHERE extname='vector'")
        ).scalar()
        assert ext is None


def test_re_upgrade_succeeds(monkeypatch):
    _alembic(["upgrade", "head"], {})
    with _engine().connect() as c:
        ext = c.execute(
            sa.text("SELECT extname FROM pg_extension WHERE extname='vector'")
        ).scalar()
        assert ext == "vector"
