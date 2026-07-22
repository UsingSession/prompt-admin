import time
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Cursor

from config import DB_CONFIG, MIGRATIONS_DIR, SCHEMA_SQL_PATH


MIGRATION_LOCK_NAME = "prompt-admin:migrations"
V2_MIGRATION_NAME = "005_prompt_model_v2.sql"
V2_DOMAIN_TABLES = frozenset(
    {
        "ai_prompt_families",
        "ai_prompts",
        "ai_prompt_variants",
        "ai_prompt_revisions",
        "ai_hooks",
        "ai_hook_revisions",
        "ai_prompt_bundles",
        "ai_prompt_bundle_revisions",
        "ai_prompt_bundle_items",
        "ai_compiled_bundle_artifacts",
    }
)


class DatabaseSchemaError(RuntimeError):
    """Raised when migration metadata and domain tables disagree."""


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


def acquire_migration_lock(cursor: Cursor) -> None:
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s));",
        (MIGRATION_LOCK_NAME,),
    )


def existing_v2_tables(cursor: Cursor) -> list[str]:
    cursor.execute(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = current_schema()
          AND tablename = ANY(%s)
        ORDER BY tablename ASC;
        """,
        (sorted(V2_DOMAIN_TABLES),),
    )
    return [row[0] for row in cursor.fetchall()]


def validate_migration_state(cursor: Cursor, migration_name: str) -> None:
    if migration_name != V2_MIGRATION_NAME:
        return

    existing_tables = existing_v2_tables(cursor)
    if not existing_tables:
        return

    table_list = ", ".join(existing_tables)
    raise DatabaseSchemaError(
        f"Cannot apply {migration_name}: Prompt Admin v2 tables exist "
        f"without migration metadata: {table_list}. Reset the incomplete "
        "Prompt Admin v2 schema before restarting the application."
    )


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

        validate_migration_state(cursor, migration_name)
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
                acquire_migration_lock(cursor)
                cursor.execute(schema_sql)
                run_migrations(cursor)
            return
        except DatabaseSchemaError:
            raise
        except Exception as exception:
            last_error = exception
            time.sleep(1)

    raise RuntimeError(f"Could not initialize database: {last_error}")