import time
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Cursor

from config import DB_CONFIG, MIGRATIONS_DIR, SCHEMA_SQL_PATH


def connect() -> psycopg.Connection:
    return psycopg.connect(**DB_CONFIG)


@contextmanager
def transaction() -> Iterator[Cursor]:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def db_health_check() -> bool:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            return cursor.fetchone()[0] == 1


def run_migrations(cursor: Cursor) -> None:
    if not MIGRATIONS_DIR.exists():
        return

    for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        migration_name = migration_path.name
        cursor.execute(
            "SELECT 1 FROM prompt_admin_migrations WHERE migration_name = %s;",
            (migration_name,),
        )
        if cursor.fetchone():
            continue

        cursor.execute(migration_path.read_text(encoding="utf-8"))
        cursor.execute(
            "INSERT INTO prompt_admin_migrations (migration_name) VALUES (%s);",
            (migration_name,),
        )


def init_database() -> None:
    schema_sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    last_error = None

    for _ in range(30):
        try:
            with transaction() as cursor:
                cursor.execute(schema_sql)
                run_migrations(cursor)
            return
        except Exception as exception:
            last_error = exception
            time.sleep(1)

    raise RuntimeError(f"Could not initialize database: {last_error}")
