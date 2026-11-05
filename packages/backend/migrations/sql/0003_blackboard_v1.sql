-- Slidoxa blackboard_v1: normalized twelve-application-table schema.
-- PostgreSQL 16 + pgvector. gen_random_uuid() is built in; uuid-ossp is not used.
-- The legacy blackboard_entry table is empty-only: the migration locks it,
-- checks its live row count, and aborts if any row exists. Downgrade recreates
-- that legacy table empty with its original nine columns.

CREATE EXTENSION IF NOT EXISTS vector;

-- Ensure the shared timestamp trigger function exists before creating triggers.
CREATE OR REPLACE FUNCTION blackboard_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- The lock closes the race between preflight counting and the eventual DROP.
LOCK TABLE public.blackboard_entry IN ACCESS EXCLUSIVE MODE;

DO $$
DECLARE
    legacy_rows bigint;
    encrypted_key_type text;
BEGIN
    SELECT count(*) INTO legacy_rows FROM public.blackboard_entry;
    IF legacy_rows <> 0 THEN
        RAISE EXCEPTION
            'blackboard_v1 aborted: public.blackboard_entry contains % row(s); preserve/map them before migration',
            legacy_rows;
    END IF;

    IF EXISTS (SELECT 1 FROM public.slidoxa_user WHERE char_length(email) > 255) THEN
        RAISE EXCEPTION
            'blackboard_v1 aborted: a slidoxa_user email exceeds users.email limit of 255 characters';
    END IF;

    -- Verify the legacy ciphertext type before the explicit TEXT -> BYTEA conversion.
    SELECT data_type INTO encrypted_key_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'slidoxa_provider_key'
      AND column_name = 'encrypted_key';

    IF encrypted_key_type IS DISTINCT FROM 'text'
       AND encrypted_key_type IS DISTINCT FROM 'character varying'
       AND encrypted_key_type IS DISTINCT FROM 'character' THEN
        RAISE EXCEPTION
            'blackboard_v1 aborted: slidoxa_provider_key.encrypted_key must be TEXT/VARCHAR before conversion; actual type=%',
            coalesce(encrypted_key_type, '<missing>');
    END IF;
END
$$;

CREATE TABLE workspaces (
    workspace_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(255) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspaces(workspace_id) ON DELETE RESTRICT,
    email varchar(255) NOT NULL UNIQUE,
    password_hash text NOT NULL,
    role varchar(32) NOT NULL DEFAULT 'editor',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_role_check CHECK (role IN ('owner', 'admin', 'editor', 'viewer'))
);
CREATE INDEX users_workspace_idx ON users(workspace_id);

CREATE TABLE provider_keys (
    key_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    provider varchar(64) NOT NULL,
    encrypted_key bytea NOT NULL,
    key_hint varchar(32) NOT NULL DEFAULT '***',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT provider_keys_user_provider_uq UNIQUE (user_id, provider)
);
CREATE INDEX provider_keys_user_idx ON provider_keys(user_id);

-- One personal workspace per existing user. IDs, password hashes, and Fernet
-- token bytes are preserved; this migration never decrypts or prints secrets.
CREATE TEMPORARY TABLE blackboard_v1_user_workspace_map (
    user_id uuid PRIMARY KEY,
    workspace_id uuid NOT NULL
) ON COMMIT DROP;

INSERT INTO blackboard_v1_user_workspace_map (user_id, workspace_id)
SELECT id, gen_random_uuid() FROM slidoxa_user;

INSERT INTO workspaces (workspace_id, name)
SELECT workspace_id, 'Personal workspace'
FROM blackboard_v1_user_workspace_map;

INSERT INTO users (user_id, workspace_id, email, password_hash, role, created_at)
SELECT old_user.id, map.workspace_id, old_user.email, old_user.password_hash,
       'editor', old_user.created_at
FROM slidoxa_user AS old_user
JOIN blackboard_v1_user_workspace_map AS map ON map.user_id = old_user.id;

INSERT INTO provider_keys
    (key_id, user_id, provider, encrypted_key, key_hint, created_at, updated_at)
SELECT old_key.id, old_key.owner_id, old_key.provider,
       convert_to(old_key.encrypted_key::text, 'UTF8'), '***',
       old_key.created_at, old_key.updated_at
FROM slidoxa_provider_key AS old_key;

DO $$
DECLARE
    old_users bigint;
    new_users bigint;
    old_keys bigint;
    new_keys bigint;
BEGIN
    SELECT count(*) INTO old_users FROM slidoxa_user;
    SELECT count(*) INTO new_users FROM users;
    SELECT count(*) INTO old_keys FROM slidoxa_provider_key;
    SELECT count(*) INTO new_keys FROM provider_keys;

    IF old_users <> new_users OR old_keys <> new_keys THEN
        RAISE EXCEPTION
            'blackboard_v1 copy count verification failed (user delta %, provider key delta %)',
            old_users - new_users, old_keys - new_keys;
    END IF;

    IF EXISTS (
        SELECT id, email, password_hash, created_at FROM slidoxa_user
        EXCEPT
        SELECT user_id, email, password_hash, created_at FROM users
    ) OR EXISTS (
        SELECT user_id, email, password_hash, created_at FROM users
        EXCEPT
        SELECT id, email, password_hash, created_at FROM slidoxa_user
    ) THEN
        RAISE EXCEPTION 'blackboard_v1 user copy content verification failed';
    END IF;

    IF EXISTS (
        SELECT id, owner_id, provider, encrypted_key, created_at, updated_at
        FROM slidoxa_provider_key
        EXCEPT
        SELECT key_id, user_id, provider, convert_from(encrypted_key, 'UTF8'), created_at, updated_at
        FROM provider_keys
    ) OR EXISTS (
        SELECT key_id, user_id, provider, convert_from(encrypted_key, 'UTF8'), created_at, updated_at
        FROM provider_keys
        EXCEPT
        SELECT id, owner_id, provider, encrypted_key, created_at, updated_at
        FROM slidoxa_provider_key
    ) THEN
        RAISE EXCEPTION 'blackboard_v1 provider-key ciphertext copy verification failed';
    END IF;
END
$$;

CREATE TABLE presentations (
    presentation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    created_by_user_id uuid REFERENCES users(user_id) ON DELETE SET NULL,
    title varchar(500) NOT NULL DEFAULT 'Untitled presentation',
    status varchar(24) NOT NULL DEFAULT 'draft',
    token_budget_max integer NOT NULL DEFAULT 45000,
    storyline_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    tokens_consumed integer NOT NULL DEFAULT 0,
    language varchar(16) DEFAULT 'en',
    theme_id varchar(64),
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT presentations_status_check
        CHECK (status IN ('draft', 'queued', 'generating', 'completed', 'failed', 'archived')),
    CONSTRAINT presentations_token_budget_check CHECK (token_budget_max > 0),
    CONSTRAINT presentations_tokens_consumed_check CHECK (tokens_consumed >= 0),
    CONSTRAINT presentations_version_check CHECK (version > 0)
);
CREATE INDEX presentations_workspace_created_idx
    ON presentations(workspace_id, created_at DESC);

CREATE TABLE source_documents (
    source_document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    presentation_id uuid NOT NULL REFERENCES presentations(presentation_id) ON DELETE CASCADE,
    uploaded_by_user_id uuid REFERENCES users(user_id) ON DELETE SET NULL,
    file_name varchar(512) NOT NULL,
    mime_type varchar(255),
    storage_uri text,
    parse_status varchar(24) NOT NULL DEFAULT 'queued',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT source_documents_parse_status_check
        CHECK (parse_status IN ('queued', 'processing', 'completed', 'failed'))
);
CREATE INDEX source_documents_presentation_idx
    ON source_documents(presentation_id, created_at DESC);

CREATE TABLE document_chunks (
    chunk_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document_id uuid NOT NULL REFERENCES source_documents(source_document_id) ON DELETE CASCADE,
    presentation_id uuid NOT NULL REFERENCES presentations(presentation_id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    page_or_slide_num integer NOT NULL,
    section_heading text,
    raw_text text NOT NULL,
    embedding vector(384),
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(raw_text, ''))
    ) STORED,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT document_chunks_index_check CHECK (chunk_index >= 0),
    CONSTRAINT document_chunks_page_check CHECK (page_or_slide_num >= 0),
    CONSTRAINT document_chunks_document_index_uq UNIQUE (source_document_id, chunk_index)
);
CREATE INDEX document_chunks_presentation_idx ON document_chunks(presentation_id);
CREATE INDEX document_chunks_search_gin_idx ON document_chunks USING gin(search_vector);
CREATE INDEX document_chunks_embedding_hnsw_idx
    ON document_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE evidence_facts (
    fact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    presentation_id uuid NOT NULL REFERENCES presentations(presentation_id) ON DELETE CASCADE,
    source_document_id uuid REFERENCES source_documents(source_document_id) ON DELETE SET NULL,
    chunk_id uuid REFERENCES document_chunks(chunk_id) ON DELETE SET NULL,
    fact_text text NOT NULL,
    page_reference varchar(64) NOT NULL,
    metric_value varchar(128),
    verification_status varchar(24) NOT NULL DEFAULT 'unverified',
    confidence numeric(5,4),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT evidence_facts_verification_status_check
        CHECK (verification_status IN ('unverified', 'verified', 'rejected')),
    CONSTRAINT evidence_facts_confidence_check
        CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1)
);
CREATE INDEX evidence_facts_presentation_idx ON evidence_facts(presentation_id);
CREATE INDEX evidence_facts_status_idx ON evidence_facts(presentation_id, verification_status);

CREATE TABLE slides (
    slide_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    presentation_id uuid NOT NULL REFERENCES presentations(presentation_id) ON DELETE CASCADE,
    slide_number integer NOT NULL,
    layout_type varchar(64) NOT NULL,
    ast_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    computed_geometry_json jsonb,
    speaker_notes text,
    version integer NOT NULL DEFAULT 1,
    status varchar(24) NOT NULL DEFAULT 'draft',
    lease_expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT slides_presentation_number_uq UNIQUE (presentation_id, slide_number),
    CONSTRAINT slides_number_check CHECK (slide_number > 0),
    CONSTRAINT slides_version_check CHECK (version > 0),
    CONSTRAINT slides_status_check CHECK (status IN ('draft', 'ready', 'approved', 'rejected'))
);
CREATE INDEX slides_presentation_idx ON slides(presentation_id, slide_number);

CREATE TABLE qa_findings (
    finding_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    presentation_id uuid NOT NULL REFERENCES presentations(presentation_id) ON DELETE CASCADE,
    slide_id uuid REFERENCES slides(slide_id) ON DELETE CASCADE,
    slide_version integer NOT NULL,
    inspector_type varchar(32) NOT NULL,
    defect_code varchar(64) NOT NULL,
    remediation_instruction text NOT NULL,
    severity varchar(16) NOT NULL,
    finding_code varchar(100) NOT NULL,
    message text NOT NULL,
    status varchar(24) NOT NULL DEFAULT 'open',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    CONSTRAINT qa_findings_slide_version_check CHECK (slide_version >= 0),
    CONSTRAINT qa_findings_severity_check
        CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    CONSTRAINT qa_findings_status_check
        CHECK (status IN ('open', 'acknowledged', 'resolved', 'ignored'))
);
CREATE INDEX qa_findings_presentation_status_idx
    ON qa_findings(presentation_id, status, severity);

CREATE TABLE job_queue (
    job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    presentation_id uuid REFERENCES presentations(presentation_id) ON DELETE CASCADE,
    job_type varchar(100) NOT NULL,
    idempotency_key varchar(128) NOT NULL UNIQUE,
    status varchar(24) NOT NULL DEFAULT 'queued',
    priority integer NOT NULL DEFAULT 0,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    result jsonb,
    attempt_count integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL DEFAULT 3,
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_until timestamptz,
    worker_id varchar(255),
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT job_queue_status_check
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT job_queue_attempts_check
        CHECK (attempt_count >= 0 AND max_attempts > 0)
);
CREATE INDEX job_queue_claim_idx
    ON job_queue(status, available_at, priority DESC, created_at);
CREATE INDEX job_queue_lease_idx ON job_queue(lease_until) WHERE status = 'running';

CREATE TABLE deck_events (
    event_id bigserial PRIMARY KEY,
    workspace_id uuid NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    presentation_id uuid NOT NULL REFERENCES presentations(presentation_id) ON DELETE CASCADE,
    slide_id uuid REFERENCES slides(slide_id) ON DELETE SET NULL,
    event_type varchar(100) NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX deck_events_replay_idx ON deck_events(presentation_id, event_id);
CREATE INDEX deck_events_workspace_idx ON deck_events(workspace_id, event_id);

CREATE TABLE agent_runs (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    presentation_id uuid REFERENCES presentations(presentation_id) ON DELETE CASCADE,
    job_id uuid REFERENCES job_queue(job_id) ON DELETE SET NULL,
    agent_name varchar(100) NOT NULL,
    model_provider varchar(64) NOT NULL,
    model_id varchar(128) NOT NULL,
    idempotency_key varchar(128) NOT NULL UNIQUE,
    prompt_tokens integer NOT NULL DEFAULT 0,
    completion_tokens integer NOT NULL DEFAULT 0,
    latency_ms integer NOT NULL DEFAULT 0,
    status varchar(24) NOT NULL DEFAULT 'queued',
    input_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    output_json jsonb,
    error_text text,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT agent_runs_status_check
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT agent_runs_usage_check
        CHECK (prompt_tokens >= 0 AND completion_tokens >= 0 AND latency_ms >= 0)
);
CREATE INDEX agent_runs_presentation_idx ON agent_runs(presentation_id, created_at DESC);
CREATE INDEX agent_runs_job_idx ON agent_runs(job_id);

-- Timestamp triggers for mutable records.
CREATE TRIGGER workspaces_set_updated_at BEFORE UPDATE ON workspaces
    FOR EACH ROW EXECUTE FUNCTION blackboard_set_updated_at();
CREATE TRIGGER provider_keys_set_updated_at BEFORE UPDATE ON provider_keys
    FOR EACH ROW EXECUTE FUNCTION blackboard_set_updated_at();
CREATE TRIGGER presentations_set_updated_at BEFORE UPDATE ON presentations
    FOR EACH ROW EXECUTE FUNCTION blackboard_set_updated_at();
CREATE TRIGGER source_documents_set_updated_at BEFORE UPDATE ON source_documents
    FOR EACH ROW EXECUTE FUNCTION blackboard_set_updated_at();
CREATE TRIGGER evidence_facts_set_updated_at BEFORE UPDATE ON evidence_facts
    FOR EACH ROW EXECUTE FUNCTION blackboard_set_updated_at();
CREATE TRIGGER slides_set_updated_at BEFORE UPDATE ON slides
    FOR EACH ROW EXECUTE FUNCTION blackboard_set_updated_at();
CREATE TRIGGER job_queue_set_updated_at BEFORE UPDATE ON job_queue
    FOR EACH ROW EXECUTE FUNCTION blackboard_set_updated_at();
CREATE TRIGGER agent_runs_set_updated_at BEFORE UPDATE ON agent_runs
    FOR EACH ROW EXECUTE FUNCTION blackboard_set_updated_at();

-- The approved DROP is intentionally last. The locked count above proves empty.
DROP TABLE public.blackboard_entry;
DROP TABLE slidoxa_provider_key;
DROP TABLE slidoxa_user;
