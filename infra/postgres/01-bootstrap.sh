#!/bin/sh
set -eu
# URL-safe credentials can be embedded unchanged in the internal psycopg DSN.
case "$FOODWISE_DB_PASSWORD" in
    ''|*[!A-Za-z0-9_-]*) echo 'FOODWISE_DB_PASSWORD must be nonempty and URL-safe (letters, digits, _ or -).' >&2; exit 1 ;;
esac
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 \
    --set=app_password="$FOODWISE_DB_PASSWORD" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE ROLE foodwise LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
REVOKE ALL ON DATABASE foodwise FROM PUBLIC;
GRANT CONNECT ON DATABASE foodwise TO foodwise;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO foodwise;
CREATE SCHEMA foodwise_checkpoints AUTHORIZATION foodwise;
SQL
