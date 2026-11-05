"""Slidoxa-owned ORM models. Not SQLModel. Not the legacy `User` table.

Tables live in the same PostgreSQL database as blackboard_entry but
under distinct names (``slidoxa_user``, ``slidoxa_provider_key``) so
there is no ambiguity about what belongs to the inherited Presenton
schema versus the Slidoxa one.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.api.db import Base


class User(Base):
    __tablename__ = "slidoxa_user"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    keys: Mapped[list["ProviderKey"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class ProviderKey(Base):
    __tablename__ = "slidoxa_provider_key"
    __table_args__ = (
        UniqueConstraint("owner_id", "provider", name="slidoxa_provider_key_owner_provider_uq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slidoxa_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    owner: Mapped[User] = relationship(back_populates="keys")
