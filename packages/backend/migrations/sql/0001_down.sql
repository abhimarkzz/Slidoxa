-- Slidoxa Blackboard v1 — downgrade.
--
-- Drops ONLY the objects created by 0001.sql, in reverse order.
-- Never issue DROP SCHEMA public CASCADE: the public schema may hold
-- other Slidoxa or operator-owned objects.

DROP TRIGGER IF EXISTS blackboard_entry_set_updated_at ON blackboard_entry;
DROP FUNCTION IF EXISTS blackboard_set_updated_at();

DROP INDEX IF EXISTS blackboard_entry_embedding_hnsw_idx;
DROP INDEX IF EXISTS blackboard_entry_owner_kind_live_idx;
DROP INDEX IF EXISTS blackboard_entry_owner_live_idx;

DROP TABLE IF EXISTS blackboard_entry;

DROP EXTENSION IF EXISTS vector;
