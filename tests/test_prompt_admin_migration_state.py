import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from psycopg import sql

from db import DatabaseSchemaError, connect, init_database


DROP_ORDER = (
    "ai_compiled_bundle_artifacts",
    "ai_prompt_bundle_items",
    "ai_prompt_bundle_revisions",
    "ai_prompt_bundles",
    "ai_hook_revisions",
    "ai_hooks",
    "ai_prompt_revisions",
    "ai_prompt_variants",
    "ai_prompts",
    "ai_prompt_families",
    "prompt_admin_migrations",
)


class PromptAdminMigrationStateTests(unittest.TestCase):
    def setUp(self):
        self.reset_database()

    def tearDown(self):
        self.reset_database()

    def reset_database(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                for table_name in DROP_ORDER:
                    cursor.execute(
                        sql.SQL("DROP TABLE IF EXISTS {} CASCADE;").format(
                            sql.Identifier(table_name)
                        )
                    )
            connection.commit()

    def migration_count(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM prompt_admin_migrations;"
                )
                return cursor.fetchone()[0]

    def test_concurrent_initialization_is_serialized(self):
        barrier = threading.Barrier(2)

        def initialize():
            barrier.wait(timeout=5)
            init_database()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(initialize) for _ in range(2)]
            for future in futures:
                future.result(timeout=15)

        self.assertEqual(self.migration_count(), 1)

    def test_existing_v2_table_without_metadata_is_rejected(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "CREATE TABLE ai_hooks (id BIGSERIAL PRIMARY KEY);"
                )
            connection.commit()

        with self.assertRaisesRegex(
            DatabaseSchemaError,
            "ai_hooks",
        ):
            init_database()

    def test_missing_v2_table_with_metadata_is_rejected(self):
        init_database()

        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE ai_hooks CASCADE;")
            connection.commit()

        with self.assertRaisesRegex(
            DatabaseSchemaError,
            "ai_hooks",
        ):
            init_database()


if __name__ == "__main__":
    unittest.main()
