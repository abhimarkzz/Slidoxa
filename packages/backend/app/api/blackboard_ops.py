"""Transactional Blackboard operations for optimistic slide updates and jobs."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class StaleSlideVersion(RuntimeError):
    """Raised when a slide update's expected version no longer matches."""

    slide_id: uuid.UUID
    expected_version: int
    latest_version: int | None

    def __str__(self) -> str:
        return (
            f"slide {self.slide_id} is stale: expected version {self.expected_version}, "
            f"latest version {self.latest_version}"
        )


def update_slide_optimistically(
    session: Session,
    *,
    slide_id: uuid.UUID,
    expected_version: int,
    ast_json: dict[str, Any],
) -> tuple[int, int]:
    """Perform compare-and-swap slide update and append an outbox event.

    The caller owns the transaction and must commit a successful update.
    A zero-row UPDATE is a stale write; the session is rolled back before
    reading the latest version and raising StaleSlideVersion.
    """
    updated = session.execute(
        text(
            """
            UPDATE slides
               SET ast_json = CAST(:ast_json AS jsonb),
                   version = version + 1,
                   updated_at = now()
             WHERE slide_id = :slide_id
               AND version = :expected_version
         RETURNING presentation_id, version
            """
        ),
        {
            "ast_json": json.dumps(ast_json),
            "slide_id": slide_id,
            "expected_version": expected_version,
        },
    ).mappings().one_or_none()

    if updated is None:
        session.rollback()
        latest_version = session.execute(
            text("SELECT version FROM slides WHERE slide_id = :slide_id"),
            {"slide_id": slide_id},
        ).scalar_one_or_none()
        raise StaleSlideVersion(
            slide_id=slide_id,
            expected_version=expected_version,
            latest_version=latest_version,
        )

    presentation = session.execute(
        text("SELECT workspace_id FROM presentations WHERE presentation_id = :presentation_id"),
        {"presentation_id": updated["presentation_id"]},
    ).mappings().one()

    event_payload = {
        "slide_id": str(slide_id),
        "version": int(updated["version"]),
    }
    event_id = session.execute(
        text(
            """
            INSERT INTO deck_events
                (workspace_id, presentation_id, slide_id, event_type, payload)
            VALUES
                (:workspace_id, :presentation_id, :slide_id, 'slide.updated', CAST(:payload AS jsonb))
            RETURNING event_id
            """
        ),
        {
            "workspace_id": presentation["workspace_id"],
            "presentation_id": updated["presentation_id"],
            "slide_id": slide_id,
            "payload": json.dumps(event_payload),
        },
    ).scalar_one()

    # PostgreSQL delivers NOTIFY only when the enclosing transaction commits.
    session.execute(
        text("SELECT pg_notify('deck_channel', :payload)"),
        {
            "payload": json.dumps(
                {
                    "event_id": int(event_id),
                    "presentation_id": str(updated["presentation_id"]),
                }
            )
        },
    )
    return int(updated["version"]), int(event_id)


def claim_next_job(session: Session, worker_id: str) -> dict[str, Any] | None:
    """Claim a queued/expired job with SKIP LOCKED and a 60-second lease."""
    statement = text(
        """
        WITH candidate AS (
            SELECT job_id
              FROM job_queue
             WHERE available_at <= now()
               AND attempt_count < max_attempts
               AND (
                    status = 'queued'
                    OR (status = 'running' AND lease_until < now())
               )
             ORDER BY priority DESC, available_at ASC, created_at ASC
             FOR UPDATE SKIP LOCKED
             LIMIT 1
        )
        UPDATE job_queue AS job
           SET status = 'running',
               worker_id = :worker_id,
               lease_until = now() + interval '60 seconds',
               attempt_count = job.attempt_count + 1,
               updated_at = now()
          FROM candidate
         WHERE job.job_id = candidate.job_id
        RETURNING job.*
        """
    )
    row = session.execute(statement, {"worker_id": worker_id}).mappings().one_or_none()
    return dict(row) if row is not None else None
