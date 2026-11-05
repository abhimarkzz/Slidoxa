-- Slidoxa Phase 2 Step 12: native user + encrypted provider-key tables.
--
-- Separate from blackboard_entry (migration 0001) and from the
-- inherited Presenton `User` table (which lives in the legacy SQLite
-- database, not here). gen_random_uuid() is available without any
-- extension on PostgreSQL 13+.

CREATE TABLE IF NOT EXISTS slidoxa_user (
    id            uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    email         varchar(320) NOT NULL UNIQUE,
    password_hash text         NOT NULL,
    created_at    timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS slidoxa_provider_key (
    id             uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id       uuid         NOT NULL REFERENCES slidoxa_user(id) ON DELETE CASCADE,
    provider       varchar(64)  NOT NULL,
    encrypted_key  text         NOT NULL,
    created_at     timestamptz  NOT NULL DEFAULT now(),
    updated_at     timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT slidoxa_provider_key_owner_provider_uq UNIQUE (owner_id, provider)
);

CREATE INDEX IF NOT EXISTS slidoxa_provider_key_owner_idx
    ON slidoxa_provider_key (owner_id);

CREATE TRIGGER slidoxa_provider_key_set_updated_at
    BEFORE UPDATE ON slidoxa_provider_key
    FOR EACH ROW
    EXECUTE FUNCTION blackboard_set_updated_at();
