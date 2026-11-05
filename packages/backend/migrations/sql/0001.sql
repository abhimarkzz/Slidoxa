-- Slidoxa Blackboard v1 — initial schema (UPGRADE).
--
-- Conservative single-table starter for the Slidoxa shared knowledge /
-- context store. No teams, ACLs, threads, attachments, or user tables
-- are introduced here — those are intentionally deferred until Slidoxa
-- owns a user model of its own (packages/backend/app/security/ is the
-- reserved scaffold for that work).
--
-- Embedding dimension: 1024. Documented, not negotiable within v1.
--   Rationale: 1024-d accommodates modern open-source embedding models
--   (mxbai-embed-large, nomic-embed-text-v1.5, bge-large-en-v1.5) and
--   is the common denominator across the embedding providers Slidoxa
--   is likely to support. Rows produced with different embedding models
--   are NOT interchangeable at retrieval time; store the model name in
--   `metadata->>'embedding_model'` and filter on it in queries. Moving
--   to a different dimension is a schema change and will require a new
--   migration (blackboard_v2) with a planned re-embedding path.
--
-- owner_id: a free-standing UUID. It is deliberately NOT a foreign
--   key to any inherited Presenton user table. When Slidoxa introduces
--   its own `user` table, a later migration can add the FK constraint
--   in-place without touching existing rows.
--
-- gen_random_uuid() is provided by PostgreSQL 13+ built-in; no
--   `uuid-ossp` extension is required.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS blackboard_entry (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id     uuid         NOT NULL,
    kind         text         NOT NULL,
    content      text         NOT NULL,
    metadata     jsonb        NOT NULL DEFAULT '{}'::jsonb,
    embedding    vector(1024),
    created_at   timestamptz  NOT NULL DEFAULT now(),
    updated_at   timestamptz  NOT NULL DEFAULT now(),
    deleted_at   timestamptz
);

-- Owner-scoped lookups skip soft-deleted rows.
CREATE INDEX IF NOT EXISTS blackboard_entry_owner_live_idx
    ON blackboard_entry (owner_id)
    WHERE deleted_at IS NULL;

-- Common filter path (owner + kind).
CREATE INDEX IF NOT EXISTS blackboard_entry_owner_kind_live_idx
    ON blackboard_entry (owner_id, kind)
    WHERE deleted_at IS NULL;

-- Approximate nearest-neighbour index for cosine similarity queries.
-- HNSW is cheap to build for small tables and query-time tunable.
CREATE INDEX IF NOT EXISTS blackboard_entry_embedding_hnsw_idx
    ON blackboard_entry USING hnsw (embedding vector_cosine_ops);

-- Keep updated_at honest without application cooperation.
CREATE OR REPLACE FUNCTION blackboard_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER blackboard_entry_set_updated_at
    BEFORE UPDATE ON blackboard_entry
    FOR EACH ROW
    EXECUTE FUNCTION blackboard_set_updated_at();
