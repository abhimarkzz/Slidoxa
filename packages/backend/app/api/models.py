"""SQLAlchemy ORM models for Slidoxa's normalized Blackboard v1 schema.

The mapped table and column names intentionally match
migrations/sql/0003_blackboard_v1.sql exactly. The legacy Presenton ORM is
kept separate and is not imported here.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID as PyUUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.api.db import Base


class Vector384(UserDefinedType):
    """PostgreSQL pgvector type for the v1 384-dimensional chunk embedding."""

    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "vector(384)"


class Workspace(Base):
    __tablename__ = "workspaces"

    workspace_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'editor', 'viewer')", name="users_role_check"),
        Index("users_workspace_idx", "workspace_id"),
    )

    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.workspace_id", ondelete="RESTRICT"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'editor'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProviderKey(Base):
    __tablename__ = "provider_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="provider_keys_user_provider_uq"),
        Index("provider_keys_user_idx", "user_id"),
    )

    key_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_hint: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'***'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Presentation(Base):
    __tablename__ = "presentations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'queued', 'generating', 'completed', 'failed', 'archived')",
            name="presentations_status_check",
        ),
        CheckConstraint("token_budget_max > 0", name="presentations_token_budget_check"),
        CheckConstraint("tokens_consumed >= 0", name="presentations_tokens_consumed_check"),
        CheckConstraint("version > 0", name="presentations_version_check"),
        Index("presentations_workspace_created_idx", "workspace_id", desc("created_at")),
    )

    presentation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, server_default=text("'Untitled presentation'")
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'draft'"))
    token_budget_max: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("45000"))
    storyline_json: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    tokens_consumed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    language: Mapped[str | None] = mapped_column(String(16), server_default=text("'en'"))
    theme_id: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        CheckConstraint(
            "parse_status IN ('queued', 'processing', 'completed', 'failed')",
            name="source_documents_parse_status_check",
        ),
        Index("source_documents_presentation_idx", "presentation_id", desc("created_at")),
    )

    source_document_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presentations.presentation_id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    storage_uri: Mapped[str | None] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'queued'")
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("source_document_id", "chunk_index", name="document_chunks_document_index_uq"),
        CheckConstraint("chunk_index >= 0", name="document_chunks_index_check"),
        CheckConstraint("page_or_slide_num >= 0", name="document_chunks_page_check"),
        Index("document_chunks_presentation_idx", "presentation_id"),
        Index("document_chunks_search_gin_idx", "search_vector", postgresql_using="gin"),
        Index(
            "document_chunks_embedding_hnsw_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    chunk_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    source_document_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_documents.source_document_id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presentations.presentation_id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_or_slide_num: Mapped[int] = mapped_column(Integer, nullable=False)
    section_heading: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any | None] = mapped_column(Vector384())
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', coalesce(raw_text, ''))", persisted=True),
        nullable=False,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidenceFact(Base):
    __tablename__ = "evidence_facts"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'rejected')",
            name="evidence_facts_verification_status_check",
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="evidence_facts_confidence_check",
        ),
        Index("evidence_facts_presentation_idx", "presentation_id"),
        Index("evidence_facts_status_idx", "presentation_id", "verification_status"),
    )

    fact_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    presentation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presentations.presentation_id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_documents.source_document_id", ondelete="SET NULL")
    )
    chunk_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.chunk_id", ondelete="SET NULL")
    )
    fact_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[str | None] = mapped_column(String(128))
    verification_status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'unverified'")
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Slide(Base):
    __tablename__ = "slides"
    __table_args__ = (
        UniqueConstraint("presentation_id", "slide_number", name="slides_presentation_number_uq"),
        CheckConstraint("slide_number > 0", name="slides_number_check"),
        CheckConstraint("version > 0", name="slides_version_check"),
        CheckConstraint("status IN ('draft', 'ready', 'approved', 'rejected')", name="slides_status_check"),
        Index("slides_presentation_idx", "presentation_id", "slide_number"),
    )

    slide_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    presentation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presentations.presentation_id", ondelete="CASCADE"), nullable=False
    )
    slide_number: Mapped[int] = mapped_column(Integer, nullable=False)
    layout_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ast_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    computed_geometry_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    speaker_notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'draft'"))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class QAFinding(Base):
    __tablename__ = "qa_findings"
    __table_args__ = (
        CheckConstraint("slide_version >= 0", name="qa_findings_slide_version_check"),
        CheckConstraint(
            "severity IN ('info', 'low', 'medium', 'high', 'critical')",
            name="qa_findings_severity_check",
        ),
        CheckConstraint("status IN ('open', 'acknowledged', 'resolved', 'ignored')", name="qa_findings_status_check"),
        Index("qa_findings_presentation_status_idx", "presentation_id", "status", "severity"),
    )

    finding_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    presentation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presentations.presentation_id", ondelete="CASCADE"), nullable=False
    )
    slide_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("slides.slide_id", ondelete="CASCADE")
    )
    slide_version: Mapped[int] = mapped_column(Integer, nullable=False)
    inspector_type: Mapped[str] = mapped_column(String(32), nullable=False)
    defect_code: Mapped[str] = mapped_column(String(64), nullable=False)
    remediation_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    finding_code: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'open'"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobQueue(Base):
    __tablename__ = "job_queue"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="job_queue_status_check",
        ),
        CheckConstraint("attempt_count >= 0 AND max_attempts > 0", name="job_queue_attempts_check"),
        Index("job_queue_claim_idx", "status", "available_at", desc("priority"), "created_at"),
        Index("job_queue_lease_idx", "lease_until", postgresql_where=text("status = 'running'")),
    )

    job_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presentations.presentation_id", ondelete="CASCADE")
    )
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'queued'"))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(255))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DeckEvent(Base):
    __tablename__ = "deck_events"
    __table_args__ = (
        Index("deck_events_replay_idx", "presentation_id", "event_id"),
        Index("deck_events_workspace_idx", "workspace_id", "event_id"),
    )

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presentations.presentation_id", ondelete="CASCADE"), nullable=False
    )
    slide_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("slides.slide_id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="agent_runs_status_check",
        ),
        CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0 AND latency_ms >= 0",
            name="agent_runs_usage_check",
        ),
        Index("agent_runs_presentation_idx", "presentation_id", desc("created_at")),
        Index("agent_runs_job_idx", "job_id"),
    )

    run_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presentations.presentation_id", ondelete="CASCADE")
    )
    job_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_queue.job_id", ondelete="SET NULL")
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'queued'"))
    input_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_text: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
