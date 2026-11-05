-- blackboard_v1 downgrade.
-- The legacy blackboard_entry restoration is EMPTY-ONLY: this migration
-- originally permits its DROP only at zero rows, and downgrade recreates
-- the same nine columns but cannot restore former blackboard_entry data.
-- Application records in the new domain tables are not silently discarded:
-- downgrade aborts if any presentation/document/chunk/fact/slide/QA/job/event/
-- agent-run rows exist. Users and encrypted provider keys are copied back.

DO $$
DECLARE
    app_rows bigint;
BEGIN
    SELECT
        (SELECT count(*) FROM presentations) +
        (SELECT count(*) FROM source_documents) +
        (SELECT count(*) FROM document_chunks) +
        (SELECT count(*) FROM evidence_facts) +
        (SELECT count(*) FROM slides) +
        (SELECT count(*) FROM qa_findings) +
        (SELECT count(*) FROM job_queue) +
        (SELECT count(*) FROM deck_events) +
        (SELECT count(*) FROM agent_runs)
    INTO app_rows;

    IF app_rows <> 0 THEN
        RAISE EXCEPTION
            'blackboard_v1 downgrade aborted: % application row(s) would be discarded; export/remove them explicitly first',
            app_rows;
    END IF;
END
$$;

CREATE TABLE slidoxa_user (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email varchar(320) NOT NULL UNIQUE,
    password_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO slidoxa_user (id, email, password_hash, created_at)
SELECT user_id, email, password_hash, created_at FROM users;

CREATE TABLE slidoxa_provider_key (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES slidoxa_user(id) ON DELETE CASCADE,
    provider varchar(64) NOT NULL,
    encrypted_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT slidoxa_provider_key_owner_provider_uq UNIQUE (owner_id, provider)
);

INSERT INTO slidoxa_provider_key
    (id, owner_id, provider, encrypted_key, created_at, updated_at)
SELECT key_id, user_id, provider, convert_from(encrypted_key, 'UTF8'), created_at, updated_at
FROM provider_keys;

CREATE INDEX slidoxa_provider_key_owner_idx ON slidoxa_provider_key(owner_id);
CREATE TRIGGER slidoxa_provider_key_set_updated_at
    BEFORE UPDATE ON slidoxa_provider_key
    FOR EACH ROW EXECUTE FUNCTION blackboard_set_updated_at();

-- Remove the twelve-table schema in dependency order.
DROP TABLE agent_runs;
DROP TABLE deck_events;
DROP TABLE qa_findings;
DROP TABLE evidence_facts;
DROP TABLE slides;
DROP TABLE document_chunks;
DROP TABLE source_documents;
DROP TABLE job_queue;
DROP TABLE presentations;
DROP TABLE provider_keys;
DROP TABLE users;
DROP TABLE workspaces;

-- EMPTY-ONLY legacy table recreation: exact columns/types from 0001.sql.
CREATE TABLE public.blackboard_entry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL,
    kind text NOT NULL,
    content text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1024),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE INDEX blackboard_entry_owner_live_idx
    ON public.blackboard_entry(owner_id)
    WHERE deleted_at IS NULL;
CREATE INDEX blackboard_entry_owner_kind_live_idx
    ON public.blackboard_entry(owner_id, kind)
    WHERE deleted_at IS NULL;
CREATE INDEX blackboard_entry_embedding_hnsw_idx
    ON public.blackboard_entry USING hnsw (embedding vector_cosine_ops);

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
    BEFORE UPDATE ON public.blackboard_entry
    FOR EACH ROW EXECUTE FUNCTION blackboard_set_updated_at();
