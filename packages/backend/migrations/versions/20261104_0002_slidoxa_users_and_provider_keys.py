"""slidoxa_users_and_provider_keys

Revision ID: 20261104_0002
Revises: 20261104_0001
Create Date: 2026-11-04
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "20261104_0002"
down_revision = "20261104_0001"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    path = _SQL_DIR / name
    statements = path.read_text(encoding="utf-8")
    if not statements.strip():
        raise RuntimeError(f"SQL file is empty: {path}")
    op.get_bind().exec_driver_sql(statements)


def upgrade() -> None:
    _run("0002.sql")


def downgrade() -> None:
    _run("0002_down.sql")
