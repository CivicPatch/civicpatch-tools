#!/bin/sh
set -eu

: "${POSTGRES_SEEDS:?ERROR: POSTGRES_SEEDS environment variable is required}"
: "${POSTGRES_USER:?ERROR: POSTGRES_USER environment variable is required}"
# DB names default to Temporal's own (temporal / temporal_visibility), so an unset env — e.g. the
# docker-compose stack — is byte-for-byte unchanged. Override to run multiple Temporals against one
# shared Postgres without the DB names colliding. MUST match the server's DBNAME / VISIBILITY_DBNAME.
: "${DBNAME:=temporal}"
: "${VISIBILITY_DBNAME:=temporal_visibility}"

echo 'Starting PostgreSQL schema setup...'
echo 'Waiting for PostgreSQL port to be available...'
nc -z -w 10 ${POSTGRES_SEEDS} ${DB_PORT:-5432}
echo 'PostgreSQL port is available'

temporal-sql-tool --plugin postgres12 --ep ${POSTGRES_SEEDS} -u ${POSTGRES_USER} -p ${DB_PORT:-5432} --db ${DBNAME} create
temporal-sql-tool --plugin postgres12 --ep ${POSTGRES_SEEDS} -u ${POSTGRES_USER} -p ${DB_PORT:-5432} --db ${DBNAME} setup-schema -v 0.0
temporal-sql-tool --plugin postgres12 --ep ${POSTGRES_SEEDS} -u ${POSTGRES_USER} -p ${DB_PORT:-5432} --db ${DBNAME} update-schema -d /etc/temporal/schema/postgresql/v12/temporal/versioned

temporal-sql-tool --plugin postgres12 --ep ${POSTGRES_SEEDS} -u ${POSTGRES_USER} -p ${DB_PORT:-5432} --db ${VISIBILITY_DBNAME} create
temporal-sql-tool --plugin postgres12 --ep ${POSTGRES_SEEDS} -u ${POSTGRES_USER} -p ${DB_PORT:-5432} --db ${VISIBILITY_DBNAME} setup-schema -v 0.0
temporal-sql-tool --plugin postgres12 --ep ${POSTGRES_SEEDS} -u ${POSTGRES_USER} -p ${DB_PORT:-5432} --db ${VISIBILITY_DBNAME} update-schema -d /etc/temporal/schema/postgresql/v12/visibility/versioned

echo 'PostgreSQL schema setup complete'
