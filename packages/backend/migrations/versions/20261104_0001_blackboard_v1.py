"""blackboard_v1

Revision ID: 20261104_0001
Revises:
Create Date: 2026-11-04

Executes the hand-authored SQL files at migrations/sql/0001.sql
(upgrade) and migrations/sql/0001_down.sql (downgrade). The SQL files
are the authoritative schema source; this Python wrapper only drives
Alembic's transaction + revision bookkeeping.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "20261104_0001"
down_revision = None
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
_UP_FILE = _SQL_DIR / "0001.sql"
_DOWN_FILE = _SQL_DIR / "0001_down.sql"


def _execute_sql_file(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"Expected SQL file is missing: {path}")
    statements = path.read_text(encoding="utf-8")
    if not statements.strip():
        raise RuntimeError(f"SQL file is empty: {path}")
    # execute_sql relies on the DBAPI handling multi-statement strings;
    # psycopg (v3) does. op.execute would wrap in a textual construct
    # that trips on multiple statements, so use the raw connection.
    bind = op.get_bind()
    bind.exec_driver_sql(statements)


def upgrade() -> None:
    _execute_sql_file(_UP_FILE)


def downgrade() -> None:
    _execute_sql_file(_DOWN_FILE)
