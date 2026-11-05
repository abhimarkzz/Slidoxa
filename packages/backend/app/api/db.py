"""Slidoxa SQLAlchemy session — isolated from inherited legacy DB.

Uses DATABASE_URL from the environment. Never imports from
packages/backend/app/legacy/. SQLModel is deliberately not used here;
Slidoxa owns its own declarative base.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Slidoxa declarative base. Metadata is isolated from legacy."""


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Slidoxa API requires an explicit "
            "psycopg URL (postgresql+psycopg://user:pw@host:5432/db)."
        )
    return url


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(_database_url(), future=True, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def session_factory() -> sessionmaker[Session]:
    engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_session() -> Iterator[Session]:
    sess = session_factory()()
    try:
        yield sess
    finally:
        sess.close()


def reset_for_tests() -> None:
    """Allow tests to rebind the engine after mutating DATABASE_URL."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
