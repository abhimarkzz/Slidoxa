#!/usr/bin/env bash
# Scratch-only blackboard_v1 migration round-trip test.
# Run from the repository root or any directory inside the checkout.
# The only read of the live application database is the pg_dump backup.
# Docker is used directly by container ID so Docker Compose does not need
# to load or interpolate any .env file.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
UP_SQL="${REPO_ROOT}/packages/backend/migrations/sql/0003_blackboard_v1.sql"
DOWN_SQL="${REPO_ROOT}/packages/backend/migrations/sql/0003_blackboard_v1_down.sql"
BACKUP_DIR="${REPO_ROOT}/backups"
BACKUP_FILE="${BACKUP_DIR}/pre_v1.dump"
BACKUP_TMP="${BACKUP_FILE}.tmp.$$"
GUARD_OUTPUT="$(mktemp "${TMPDIR:-/tmp}/blackboard-v1-down-guard.XXXXXX")"
DB_CONTAINER_ID=""
SCRATCH_CREATED=0
CURRENT_STEP="preflight"
FAIL_REPORTED=0

pass() { printf 'PASS: %s\n' "$1"; }
fail() { FAIL_REPORTED=1; printf 'FAIL: %s\n' "$1" >&2; exit 1; }

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "${status}" -ne 0 && "${FAIL_REPORTED}" -eq 0 ]]; then
        printf 'FAIL: script stopped during %s\n' "${CURRENT_STEP}" >&2
    fi
    rm -f "${BACKUP_TMP}" "${GUARD_OUTPUT}" || true
    if [[ "${SCRATCH_CREATED}" -eq 1 && -n "${DB_CONTAINER_ID}" ]]; then
        printf 'CLEANUP: dropping scratch database\n'
        if docker exec "${DB_CONTAINER_ID}" dropdb -U ogs --if-exists scratch >/dev/null 2>&1; then
            printf 'PASS: scratch database cleanup\n'
        else
            printf 'FAIL: could not drop scratch database; inspect it manually\n' >&2
            status=1
        fi
    fi
    exit "${status}"
}
trap cleanup EXIT

cd "${REPO_ROOT}"

# File checks happen before any Docker/database operation.
CURRENT_STEP="migration file preflight"
[[ -f "${UP_SQL}" ]] || fail "missing upgrade SQL: packages/backend/migrations/sql/0003_blackboard_v1.sql"
[[ -f "${DOWN_SQL}" ]] || fail "missing downgrade SQL: packages/backend/migrations/sql/0003_blackboard_v1_down.sql"
pass "required SQL files exist"

command -v docker >/dev/null 2>&1 || fail "docker CLI is not installed"
[[ ! -e "${BACKUP_FILE}" ]] || fail "backup already exists at backups/pre_v1.dump; refusing to overwrite it"
mkdir -p "${BACKUP_DIR}"

CURRENT_STEP="locate running database container"
# Resolve the already-running Compose service=db container without invoking
# Docker Compose (which would load/interpolate .env). Never start a container.
printf 'STEP: locate the already-running Presenton Compose service db\n'
DB_CONTAINER_IDS="$(docker ps \
    --filter 'label=com.docker.compose.project=presenton' \
    --filter 'label=com.docker.compose.service=db' \
    --format '{{.ID}}')"
[[ -n "${DB_CONTAINER_IDS}" ]] || fail "no running Presenton Compose service db container; start nothing automatically"
[[ "${DB_CONTAINER_IDS}" != *$'\n'* ]] || fail "multiple running Presenton Compose service db containers found"
DB_CONTAINER_ID="${DB_CONTAINER_IDS}"
pass "one running service db container identified"

CURRENT_STEP="backup live database"
# The only read of the live application database: create a custom-format dump.
printf 'STEP: backup live database ogs to backups/pre_v1.dump\n'
if docker exec -i "${DB_CONTAINER_ID}" pg_dump -U ogs -Fc -d ogs > "${BACKUP_TMP}" && [[ -s "${BACKUP_TMP}" ]]; then
    mv "${BACKUP_TMP}" "${BACKUP_FILE}"
    pass "live database backup created"
else
    fail "live database backup failed or produced an empty archive"
fi

CURRENT_STEP="create and restore scratch database"
# All subsequent schema/data operations target only the restored scratch DB.
# CREATE DATABASE is deliberately attempted directly; if scratch already
# exists PostgreSQL rejects creation and the script will not drop that DB.
printf 'STEP: create scratch database and restore backup\n'
if docker exec "${DB_CONTAINER_ID}" psql -X -q -v ON_ERROR_STOP=1 -U ogs -d postgres \
    -c 'CREATE DATABASE scratch OWNER ogs;' >/dev/null; then
    SCRATCH_CREATED=1
else
    fail "could not create scratch database (it may already exist); no existing database was dropped"
fi
if docker exec -i "${DB_CONTAINER_ID}" pg_restore -U ogs -d scratch --no-owner --exit-on-error < "${BACKUP_FILE}"; then
    pass "scratch database restored from backup"
else
    fail "restoring backup into scratch failed"
fi

psql_scratch() {
    docker exec -i "${DB_CONTAINER_ID}" psql -X -v ON_ERROR_STOP=1 -U ogs -d scratch "$@"
}

scalar_scratch() {
    psql_scratch -q -A -t -c "$1" | tr -d '[:space:]'
}

row_count() {
    local table="$1"
    scalar_scratch "SELECT count(*) FROM public.${table};"
}

assert_equal() {
    local label="$1" actual="$2" expected="$3"
    [[ "${actual}" == "${expected}" ]] || fail "${label} (expected ${expected}, got ${actual})"
    pass "${label}"
}

print_tables() {
    printf '\\dt\n'
    psql_scratch -c '\dt'
}

CURRENT_STEP="capture scratch baseline counts"
# BEFORE counts are captured only from the restored copy; display names/counts only.
printf 'STEP: capture BEFORE counts in scratch\n'
BEFORE_USERS="$(row_count slidoxa_user)"
BEFORE_KEYS="$(row_count slidoxa_provider_key)"
BEFORE_BLACKBOARD="$(row_count blackboard_entry)"
printf 'BEFORE slidoxa_user: %s\n' "${BEFORE_USERS}"
printf 'BEFORE slidoxa_provider_key: %s\n' "${BEFORE_KEYS}"
printf 'BEFORE blackboard_entry: %s\n' "${BEFORE_BLACKBOARD}"
[[ "${BEFORE_BLACKBOARD}" == "0" ]] || fail "scratch blackboard_entry is not empty; migration must not drop it"
pass "BEFORE counts captured; blackboard_entry is empty"

CURRENT_STEP="first scratch upgrade"
printf 'STEP: apply blackboard_v1 upgrade SQL to scratch\n'
if psql_scratch -1 -q -f - < "${UP_SQL}" >/dev/null; then
    pass "upgrade SQL applied to scratch"
else
    fail "upgrade SQL failed on scratch"
fi
print_tables

APP_TABLE_COUNT="$(scalar_scratch "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' AND table_name = ANY (ARRAY['workspaces','users','provider_keys','presentations','source_documents','document_chunks','evidence_facts','slides','qa_findings','job_queue','deck_events','agent_runs']);")"
AFTER_USERS="$(row_count users)"
AFTER_KEYS="$(row_count provider_keys)"
AFTER_WORKSPACES="$(row_count workspaces)"
LEGACY_TABLE_COUNT="$(scalar_scratch "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND (left(table_name, 8) = 'slidoxa_' OR table_name='blackboard_entry');")"
printf 'AFTER UPGRADE users: %s\n' "${AFTER_USERS}"
printf 'AFTER UPGRADE provider_keys: %s\n' "${AFTER_KEYS}"
printf 'AFTER UPGRADE workspaces: %s\n' "${AFTER_WORKSPACES}"
assert_equal "exactly 12 application tables exist" "${APP_TABLE_COUNT}" "12"
assert_equal "users count preserved by upgrade" "${AFTER_USERS}" "${BEFORE_USERS}"
assert_equal "provider_keys count preserved by upgrade" "${AFTER_KEYS}" "${BEFORE_KEYS}"
assert_equal "no slidoxa_* or blackboard_entry tables remain" "${LEGACY_TABLE_COUNT}" "0"

CURRENT_STEP="downgrade guard test"
# GUARD TEST: one presentation row must make the downgrade refuse to run.
printf 'STEP: prove downgrade guard rejects application rows\n'
if ! psql_scratch -1 -q -c \
    "WITH w AS (INSERT INTO workspaces(name) VALUES ('__blackboard_v1_guard_workspace__') RETURNING workspace_id) INSERT INTO presentations(workspace_id, title) SELECT workspace_id, '__blackboard_v1_guard_presentation__' FROM w;" \
    >/dev/null; then
    fail "could not insert the scratch downgrade-guard row"
fi
if psql_scratch -1 -q -f - < "${DOWN_SQL}" > "${GUARD_OUTPUT}" 2>&1; then
    fail "downgrade guard unexpectedly succeeded with a presentation row"
fi
if ! grep -Fq 'application row(s) would be discarded' "${GUARD_OUTPUT}"; then
    fail "downgrade failed, but not with the expected application-row guard message"
fi
pass "downgrade guard rejected a populated application table"

CURRENT_STEP="remove downgrade-guard row"
printf 'STEP: remove guard-test presentation/workspace from scratch\n'
if psql_scratch -1 -q -c \
    "DELETE FROM workspaces WHERE name = '__blackboard_v1_guard_workspace__';" \
    >/dev/null; then
    pass "guard-test rows removed"
else
    fail "could not remove guard-test workspace"
fi

CURRENT_STEP="scratch downgrade"
printf 'STEP: apply downgrade SQL to empty application schema\n'
if psql_scratch -1 -q -f - < "${DOWN_SQL}" >/dev/null; then
    pass "downgrade SQL applied to scratch"
else
    fail "downgrade SQL failed on empty scratch application tables"
fi
print_tables

RESTORED_USERS="$(row_count slidoxa_user)"
RESTORED_KEYS="$(row_count slidoxa_provider_key)"
RESTORED_BLACKBOARD="$(row_count blackboard_entry)"
BLACKBOARD_TABLE_EXISTS="$(scalar_scratch "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='blackboard_entry';")"
printf 'AFTER DOWNGRADE slidoxa_user: %s\n' "${RESTORED_USERS}"
printf 'AFTER DOWNGRADE slidoxa_provider_key: %s\n' "${RESTORED_KEYS}"
printf 'AFTER DOWNGRADE blackboard_entry: %s\n' "${RESTORED_BLACKBOARD}"
assert_equal "slidoxa_user count restored" "${RESTORED_USERS}" "${BEFORE_USERS}"
assert_equal "slidoxa_provider_key count restored" "${RESTORED_KEYS}" "${BEFORE_KEYS}"
assert_equal "blackboard_entry table recreated" "${BLACKBOARD_TABLE_EXISTS}" "1"
assert_equal "blackboard_entry recreated empty" "${RESTORED_BLACKBOARD}" "0"

CURRENT_STEP="scratch re-upgrade"
printf 'STEP: re-apply blackboard_v1 upgrade SQL to scratch\n'
if psql_scratch -1 -q -f - < "${UP_SQL}" >/dev/null; then
    pass "re-upgrade SQL applied to scratch"
else
    fail "re-upgrade SQL failed on scratch"
fi
print_tables

FINAL_APP_TABLE_COUNT="$(scalar_scratch "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' AND table_name = ANY (ARRAY['workspaces','users','provider_keys','presentations','source_documents','document_chunks','evidence_facts','slides','qa_findings','job_queue','deck_events','agent_runs']);")"
FINAL_USERS="$(row_count users)"
FINAL_KEYS="$(row_count provider_keys)"
FINAL_LEGACY_TABLE_COUNT="$(scalar_scratch "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND (left(table_name, 8) = 'slidoxa_' OR table_name='blackboard_entry');")"
printf 'AFTER RE-UPGRADE users: %s\n' "${FINAL_USERS}"
printf 'AFTER RE-UPGRADE provider_keys: %s\n' "${FINAL_KEYS}"
assert_equal "re-upgrade restored exactly 12 application tables" "${FINAL_APP_TABLE_COUNT}" "12"
assert_equal "re-upgrade preserved user count" "${FINAL_USERS}" "${BEFORE_USERS}"
assert_equal "re-upgrade preserved provider-key count" "${FINAL_KEYS}" "${BEFORE_KEYS}"
assert_equal "re-upgrade removed legacy table names" "${FINAL_LEGACY_TABLE_COUNT}" "0"

pass "scratch round-trip completed"
printf 'NOTE: backup retained at backups/pre_v1.dump\n'
printf 'NOTE: all migration changes in this script were applied only to scratch\n'
