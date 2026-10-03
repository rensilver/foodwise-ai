"""Initialize only a disposable foodwise_test database for P01-07 verification."""

import os

import psycopg
from psycopg.conninfo import conninfo_to_dict


def main() -> None:
    dsn = os.environ["TEST_DATABASE_ADMIN_URL"]
    details = conninfo_to_dict(dsn)
    if details.get("dbname") != "foodwise_test" or details.get("host") not in {
        "localhost",
        "127.0.0.1",
    }:
        raise SystemExit("Bootstrap requires a localhost database named foodwise_test.")
    with psycopg.connect(dsn, connect_timeout=5) as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        connection.execute(
            "CREATE ROLE foodwise_test_app LOGIN "
            "PASSWORD 'synthetic-ci-application-password' "
            "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION"
        )
        connection.execute("REVOKE ALL ON DATABASE foodwise_test FROM PUBLIC")
        connection.execute(
            "GRANT CONNECT ON DATABASE foodwise_test TO foodwise_test_app"
        )
        connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        connection.execute("GRANT USAGE, CREATE ON SCHEMA public TO foodwise_test_app")
        connection.execute(
            "CREATE SCHEMA foodwise_checkpoints AUTHORIZATION foodwise_test_app"
        )
    print("Initialized disposable PostgreSQL/pgvector test database and limited role.")


if __name__ == "__main__":
    main()
