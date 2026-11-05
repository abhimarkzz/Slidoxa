"""Alembic env for the NEW Slidoxa database.

Isolation contract:
- This module must NOT import legacy SQLModel metadata from
  packages/backend/app/legacy/. If a future autogenerate pass needs
  metadata, import ONLY Slidoxa-authored models (currently none exist).
- The engine is constructed from DATABASE_URL in the environment;
  sqlalchemy.url in alembic.ini is intentionally blank.
- target_metadata is None so autogenerate is a no-op; migrations are
  hand-authored SQL files under migrations/sql/.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Hand-authored migrations only — no model autogeneration.
target_metadata = None


def _resolved_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Slidoxa Alembic env requires an "
            "explicit psycopg URL, e.g. "
            "postgresql+psycopg://ogs:...@db:5432/ogs"
        )
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_resolved_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _resolved_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
