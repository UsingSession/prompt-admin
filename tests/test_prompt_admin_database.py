import unittest

from fastapi.testclient import TestClient
from psycopg import IntegrityError, sql
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Jsonb

from app import create_app
from db import connect, init_database, transaction
from repositories.artifact_repository import (
    artifact_exists_for_bundle_revision,
)
from repositories.bundle_repository import (
    bundle_exists,
    bundle_revision_exists,
    next_bundle_revision_number,
)
from repositories.hook_repository import (
    hook_exists,
    next_hook_revision_number,
)
from repositories.prompt_repository import (
    next_prompt_revision_number,
    prompt_exists,
    prompt_revision_exists,
)


EXPECTED_TABLES = {
    "prompt_admin_migrations",
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

EXPECTED_INDEXES = {
    "ai_prompt_families_active_idx",
    "ai_prompts_active_idx",
    "ai_prompts_prompt_family_id_idx",
    "ai_prompt_variants_active_idx",
    "ai_prompt_variants_status_idx",
    "ai_hooks_active_idx",
    "ai_prompt_bundles_active_idx",
    "ai_prompt_bundle_revisions_status_idx",
    "ai_prompt_bundle_revisions_published_idx",
    "ai_prompt_bundle_items_order_idx",
    "ai_prompt_bundle_items_prompt_revision_id_idx",
}

LEGACY_TABLES = {
    "ai_system_prompts",
    "ai_system_prompt_versions",
    "ai_prompt_hooks",
    "ai_prompt_hook_versions",
}

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
    "ai_prompt_hook_versions",
    "ai_prompt_hooks",
    "ai_system_prompt_versions",
    "ai_system_prompts",
    "prompt_admin_migrations",
)

DOMAIN_TABLES = EXPECTED_TABLES - {"prompt_admin_migrations"}


class PromptAdminDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.reset_database()
        init_database()

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

    def table_names(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public';
                    """
                )
                return {row[0] for row in cursor.fetchall()}

    def create_prompt_graph(self):
        with transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO ai_prompt_families (
                    family_key,
                    display_name
                )
                VALUES (%s, %s)
                RETURNING id;
                """,
                ("family.test", "Test family"),
            )
            family_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO ai_prompts (
                    prompt_key,
                    display_name,
                    prompt_family_id
                )
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                ("prompt.test", "Test prompt", family_id),
            )
            prompt_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO ai_prompt_variants (
                    prompt_id,
                    variant_key,
                    display_name,
                    status
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (prompt_id, "baseline", "Baseline", "available"),
            )
            variant_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO ai_prompt_revisions (
                    variant_id,
                    revision_number,
                    system_prompt
                )
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (variant_id, 1, "System prompt"),
            )
            revision_id = cursor.fetchone()[0]

        return {
            "family_id": family_id,
            "prompt_id": prompt_id,
            "variant_id": variant_id,
            "revision_id": revision_id,
        }

    def create_bundle_graph(self, prompt_revision_id):
        with transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO ai_prompt_bundles (
                    bundle_key,
                    display_name
                )
                VALUES (%s, %s)
                RETURNING id;
                """,
                ("bundle.test", "Test bundle"),
            )
            bundle_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO ai_prompt_bundle_revisions (
                    bundle_id,
                    revision_number,
                    status
                )
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (bundle_id, 1, "draft"),
            )
            bundle_revision_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO ai_prompt_bundle_items (
                    bundle_revision_id,
                    role_key,
                    prompt_revision_id
                )
                VALUES (%s, %s, %s);
                """,
                (bundle_revision_id, "system", prompt_revision_id),
            )

        return {
            "bundle_id": bundle_id,
            "bundle_revision_id": bundle_revision_id,
        }

    def test_fresh_database_contains_only_v2_tables(self):
        table_names = self.table_names()

        self.assertEqual(table_names, EXPECTED_TABLES)
        self.assertTrue(LEGACY_TABLES.isdisjoint(table_names))

    def test_expected_indexes_exist(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public';
                    """
                )
                index_names = {row[0] for row in cursor.fetchall()}

        self.assertTrue(EXPECTED_INDEXES.issubset(index_names))

    def test_migration_metadata_records_v2_baseline(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT migration_name
                    FROM prompt_admin_migrations
                    ORDER BY migration_name;
                    """
                )
                migrations = [row[0] for row in cursor.fetchall()]

        self.assertEqual(migrations, ["005_prompt_model_v2.sql"])

    def test_fresh_database_has_no_domain_seed_data(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                for table_name in sorted(DOMAIN_TABLES):
                    cursor.execute(
                        sql.SQL("SELECT COUNT(*) FROM {};").format(
                            sql.Identifier(table_name)
                        )
                    )
                    self.assertEqual(cursor.fetchone()[0], 0, table_name)

    def test_repeated_initialization_is_idempotent(self):
        init_database()

        self.assertEqual(self.table_names(), EXPECTED_TABLES)
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM prompt_admin_migrations;"
                )
                self.assertEqual(cursor.fetchone()[0], 1)

    def test_application_starts_with_empty_v2_domain(self):
        with TestClient(create_app()) as client:
            response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": True})

    def test_foreign_keys_reject_missing_parents(self):
        with self.assertRaises(ForeignKeyViolation):
            with transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_prompt_variants (
                        prompt_id,
                        variant_key,
                        display_name,
                        status
                    )
                    VALUES (%s, %s, %s, %s);
                    """,
                    (999999, "baseline", "Baseline", "draft"),
                )

    def test_unique_constraints_reject_duplicate_child_keys(self):
        ids = self.create_prompt_graph()

        with self.assertRaises(UniqueViolation):
            with transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_prompt_variants (
                        prompt_id,
                        variant_key,
                        display_name,
                        status
                    )
                    VALUES (%s, %s, %s, %s);
                    """,
                    (
                        ids["prompt_id"],
                        "baseline",
                        "Duplicate baseline",
                        "draft",
                    ),
                )

    def test_check_constraints_protect_domain_invariants(self):
        with self.assertRaises(CheckViolation):
            with transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_prompt_families (
                        family_key,
                        display_name
                    )
                    VALUES (%s, %s);
                    """,
                    ("   ", "Invalid family"),
                )

        ids = self.create_prompt_graph()
        with self.assertRaises(CheckViolation):
            with transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_prompt_variants (
                        prompt_id,
                        variant_key,
                        display_name,
                        status
                    )
                    VALUES (%s, %s, %s, %s);
                    """,
                    (
                        ids["prompt_id"],
                        "candidate",
                        "Candidate",
                        "invalid",
                    ),
                )

        with self.assertRaises(CheckViolation):
            with transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_prompt_revisions (
                        variant_id,
                        revision_number,
                        system_prompt
                    )
                    VALUES (%s, %s, %s);
                    """,
                    (ids["variant_id"], 0, "Invalid revision"),
                )

    def test_bundle_publication_and_ordering_constraints(self):
        ids = self.create_prompt_graph()
        bundle = self.create_bundle_graph(ids["revision_id"])

        with self.assertRaises(CheckViolation):
            with transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_prompt_bundle_revisions (
                        bundle_id,
                        revision_number,
                        status
                    )
                    VALUES (%s, %s, %s);
                    """,
                    (bundle["bundle_id"], 2, "published"),
                )

        with self.assertRaises(CheckViolation):
            with transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_prompt_bundle_items (
                        bundle_revision_id,
                        role_key,
                        prompt_revision_id,
                        position
                    )
                    VALUES (%s, %s, %s, %s);
                    """,
                    (
                        bundle["bundle_revision_id"],
                        "invalid",
                        ids["revision_id"],
                        -1,
                    ),
                )

    def test_artifact_constraints_allow_one_object_per_revision(self):
        ids = self.create_prompt_graph()
        bundle = self.create_bundle_graph(ids["revision_id"])

        with transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO ai_compiled_bundle_artifacts (
                    bundle_revision_id,
                    content_hash,
                    compiled_payload
                )
                VALUES (%s, %s, %s);
                """,
                (
                    bundle["bundle_revision_id"],
                    "sha256:test",
                    Jsonb({"prompts": {}}),
                ),
            )

        with self.assertRaises(UniqueViolation):
            with transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_compiled_bundle_artifacts (
                        bundle_revision_id,
                        content_hash,
                        compiled_payload
                    )
                    VALUES (%s, %s, %s);
                    """,
                    (
                        bundle["bundle_revision_id"],
                        "sha256:duplicate",
                        Jsonb({"prompts": {}}),
                    ),
                )

        with transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO ai_prompt_bundle_revisions (
                    bundle_id,
                    revision_number,
                    status
                )
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (bundle["bundle_id"], 2, "draft"),
            )
            second_revision_id = cursor.fetchone()[0]

        with self.assertRaises(CheckViolation):
            with transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_compiled_bundle_artifacts (
                        bundle_revision_id,
                        content_hash,
                        compiled_payload
                    )
                    VALUES (%s, %s, %s);
                    """,
                    (
                        second_revision_id,
                        "sha256:list",
                        Jsonb([]),
                    ),
                )

    def test_on_delete_rules_preserve_immutable_history(self):
        ids = self.create_prompt_graph()
        self.create_bundle_graph(ids["revision_id"])

        with transaction() as cursor:
            cursor.execute(
                "DELETE FROM ai_prompt_families WHERE id = %s;",
                (ids["family_id"],),
            )
            cursor.execute(
                "SELECT prompt_family_id FROM ai_prompts WHERE id = %s;",
                (ids["prompt_id"],),
            )
            self.assertIsNone(cursor.fetchone()[0])

        with self.assertRaises(ForeignKeyViolation):
            with transaction() as cursor:
                cursor.execute(
                    "DELETE FROM ai_prompts WHERE id = %s;",
                    (ids["prompt_id"],),
                )

        with self.assertRaises(ForeignKeyViolation):
            with transaction() as cursor:
                cursor.execute(
                    """
                    DELETE FROM ai_prompt_revisions
                    WHERE id = %s;
                    """,
                    (ids["revision_id"],),
                )

    def test_transaction_rolls_back_and_closes_cleanly(self):
        with self.assertRaises(RuntimeError):
            with transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_prompt_families (
                        family_key,
                        display_name
                    )
                    VALUES (%s, %s);
                    """,
                    ("family.rollback", "Rollback family"),
                )
                raise RuntimeError("rollback")

        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM ai_prompt_families
                    WHERE family_key = %s;
                    """,
                    ("family.rollback",),
                )
                self.assertEqual(cursor.fetchone()[0], 0)

    def test_repository_foundation_queries_v2_schema(self):
        ids = self.create_prompt_graph()
        bundle = self.create_bundle_graph(ids["revision_id"])

        with transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO ai_hooks (
                    hook_key,
                    display_name
                )
                VALUES (%s, %s)
                RETURNING id;
                """,
                ("hook.test", "Test hook"),
            )
            hook_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO ai_hook_revisions (
                    hook_id,
                    revision_number,
                    hook_group,
                    hook_content
                )
                VALUES (%s, %s, %s, %s);
                """,
                (hook_id, 1, "hook_test", "Hook content"),
            )

            self.assertTrue(prompt_exists(cursor, ids["prompt_id"]))
            self.assertTrue(
                prompt_revision_exists(cursor, ids["revision_id"])
            )
            self.assertEqual(
                next_prompt_revision_number(cursor, ids["variant_id"]),
                2,
            )
            self.assertTrue(hook_exists(cursor, hook_id))
            self.assertEqual(next_hook_revision_number(cursor, hook_id), 2)
            self.assertTrue(bundle_exists(cursor, bundle["bundle_id"]))
            self.assertTrue(
                bundle_revision_exists(
                    cursor,
                    bundle["bundle_revision_id"],
                )
            )
            self.assertEqual(
                next_bundle_revision_number(cursor, bundle["bundle_id"]),
                2,
            )
            self.assertFalse(
                artifact_exists_for_bundle_revision(
                    cursor,
                    bundle["bundle_revision_id"],
                )
            )


if __name__ == "__main__":
    unittest.main()
