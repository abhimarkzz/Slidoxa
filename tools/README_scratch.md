# Blackboard v1 scratch round-trip

Run this script from the repository root (or any directory inside the checkout):

```bash
bash tools/scratch_roundtrip.sh
```

## What it does

1. Verifies that both migration SQL files exist before starting any Docker/database operation.
2. Finds the already-running Docker container carrying the Compose labels `com.docker.compose.project=presenton` and `com.docker.compose.service=db`. It does not start or recreate the service.
3. Creates `backups/pre_v1.dump` with `pg_dump -U ogs -Fc -d ogs`. This is the script's only read of the live application database. The script refuses to overwrite an existing backup.
4. Creates a new database named `scratch` and restores the dump into it.
5. Prints the pre-migration counts for `slidoxa_user`, `slidoxa_provider_key`, and `blackboard_entry` only.
6. Applies `0003_blackboard_v1.sql` to `scratch` in one transaction, prints `\\dt`, and validates the twelve expected application tables, preserved user/provider-key counts, and removal of old table names.
7. Inserts a temporary presentation and confirms that the downgrade refuses to proceed with the expected `application row(s) would be discarded` message.
8. Removes the guard-test workspace, applies the downgrade, and verifies the legacy auth-table counts plus an empty recreated `blackboard_entry`.
9. Applies the upgrade SQL again and rechecks the twelve-table schema and preserved counts.
10. Drops the `scratch` database on exit, including on failure. The backup remains at `backups/pre_v1.dump`.

All migration SQL execution and all row-count/schema inspection after restoration target `scratch`, never `ogs`. The only live application database read is the `pg_dump` command. The script uses `docker ps`/`docker exec` rather than Docker Compose commands so it does not cause Compose to load or interpolate `.env` files. It never reads, displays, sources, or modifies `.env` files. Do not commit the backup file.

## Safety notes

- The script refuses to run if `backups/pre_v1.dump` already exists. Preserve that file and choose a safe archival location before intentionally making another backup.
- The script refuses to use an already-existing database named `scratch`; PostgreSQL rejects `CREATE DATABASE scratch`, and the script does not claim ownership or drop that pre-existing database.
- The script does not start any Docker container. The intended Presenton `db` service container must already be running. It must be the only running container with the two labels described above.
- The script verifies that restored `blackboard_entry` is empty before attempting the upgrade. The migration itself also takes an exclusive lock and rechecks this condition.
- The downgrade guard is expected to fail in the deliberate presentation-row test. That expected failure is reported as a PASS only when the required error phrase is present.
- This is a direct SQL round-trip test, not an Alembic revision test. It does not alter `alembic_version` in `scratch`.
- If any step fails, the script exits and its EXIT trap attempts to drop only the `scratch` database it created. The pre-migration backup is retained.
