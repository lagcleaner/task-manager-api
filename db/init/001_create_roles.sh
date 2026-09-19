#!/usr/bin/env bash
# Runs once, automatically, on first cluster init (official postgres image
# behavior for anything under /docker-entrypoint-initdb.d). Replaces "use the
# bootstrap superuser for everything" with two least-privilege roles:
#   - MIGRATOR: may run DDL, used only by the one-shot `migrate` service
#   - APP: DML only, used by the always-running `api` service
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE ${POSTGRES_MIGRATOR_USER} LOGIN PASSWORD '${POSTGRES_MIGRATOR_PASSWORD}';
    CREATE ROLE ${POSTGRES_APP_USER} LOGIN PASSWORD '${POSTGRES_APP_PASSWORD}';

    GRANT ALL PRIVILEGES ON SCHEMA public TO ${POSTGRES_MIGRATOR_USER};

    GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_APP_USER};
    GRANT USAGE ON SCHEMA public TO ${POSTGRES_APP_USER};

    -- Tables/sequences created later by the migrator (via Alembic) automatically
    -- grant the app role DML rights only -- never CREATE/ALTER/DROP.
    ALTER DEFAULT PRIVILEGES FOR ROLE ${POSTGRES_MIGRATOR_USER} IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${POSTGRES_APP_USER};
    ALTER DEFAULT PRIVILEGES FOR ROLE ${POSTGRES_MIGRATOR_USER} IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO ${POSTGRES_APP_USER};
EOSQL
