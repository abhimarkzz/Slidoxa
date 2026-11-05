"""blackboard_v1 normalized schema migration.

Revision ID: blackboard_v1
Revises: 20261104_0002

The SQL files are the authoritative schema definition. This wrapper
executes each file through the migration connection so Alembic records
one revision for the complete change.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "blackboard_v1"
down_revision = "20261104_0002"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
_UP_FILE = _SQL_DIR / "0003_blackboard_v1.sql"
_DOWN_FILE = _SQL_DIR / "0003_blackboard_v1_down.sql"


def _execute_sql_file(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"Expected SQL migration file is missing: {path}")
    sql = path.read_text(encoding="utf-8")
    if not sql.strip():
        raise RuntimeError(f"SQL migration file is empty: {path}")
    # No params passed, so psycopg does not treat % as a placeholder.
    raw = op.get_bind().connection  # DBAPI connection, same transaction
    with raw.cursor() as cur:
        cur.execute(sql)


def upgrade() -> None:
    _execute_sql_file(_UP_FILE)


def downgrade() -> None:
    _execute_sql_file(_DOWN_FILE)
