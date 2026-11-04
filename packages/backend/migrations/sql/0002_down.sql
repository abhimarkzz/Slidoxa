-- Slidoxa Phase 2 Step 12 downgrade.

DROP TRIGGER IF EXISTS slidoxa_provider_key_set_updated_at ON slidoxa_provider_key;
DROP INDEX IF EXISTS slidoxa_provider_key_owner_idx;
DROP TABLE IF EXISTS slidoxa_provider_key;
DROP TABLE IF EXISTS slidoxa_user;
