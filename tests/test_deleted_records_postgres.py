import unittest

from fastapi.testclient import TestClient
from psycopg import sql

from app import create_app
from db import connect, init_database
from errors import PromptAdminError
from schemas.prompt import (
    FamilyCreate,
    PromptCreate,
    PromptRevisionCreate,
    VariantCreate,
)
from services import deleted_record_service, prompt_service


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


class DeletedRecordsPostgresTests(unittest.TestCase):
    def setUp(self):
        self.reset_database()
        init_database()
        self.client = TestClient(
            create_app(initialize_database=False),
            raise_server_exceptions=False,
        )
        self.addCleanup(self.client.close)

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

    def create_prompt_history(self, prompt_key="prompt.deleted"):
        prompt_service.create_prompt(
            PromptCreate(
                prompt_key=prompt_key,
                display_name="Deleted prompt",
            )
        )
        prompt_service.create_variant(
            prompt_key,
            VariantCreate(
                variant_key="baseline",
                display_name="Baseline",
                status="available",
            ),
        )
        return prompt_service.create_revision(
            prompt_key,
            "baseline",
            PromptRevisionCreate(system_prompt="System prompt"),
        )

    def test_permanent_prompt_delete_releases_stable_key(self):
        self.create_prompt_history()
        prompt_service.delete_prompt("prompt.deleted")

        response = self.client.post(
            "/deleted/prompts/prompt.deleted/permanent-delete",
            data={"confirm_key": "prompt.deleted"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        recreated = prompt_service.create_prompt(
            PromptCreate(
                prompt_key="prompt.deleted",
                display_name="Recreated prompt",
            )
        )
        self.assertEqual(recreated["prompt_key"], "prompt.deleted")
        self.assertEqual(
            prompt_service.list_variants("prompt.deleted"),
            [],
        )

    def test_permanent_family_delete_detaches_prompts_and_releases_key(self):
        prompt_service.create_family(
            FamilyCreate(
                family_key="family.deleted",
                display_name="Deleted family",
            )
        )
        prompt_service.create_prompt(
            PromptCreate(
                prompt_key="prompt.member",
                display_name="Family member",
                family_key="family.deleted",
            )
        )
        prompt_service.delete_family("family.deleted")

        response = self.client.post(
            "/deleted/families/family.deleted/permanent-delete",
            data={"confirm_key": "family.deleted"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertIsNone(
            prompt_service.get_prompt("prompt.member")["family_key"]
        )
        recreated = prompt_service.create_family(
            FamilyCreate(
                family_key="family.deleted",
                display_name="Recreated family",
            )
        )
        self.assertEqual(recreated["family_key"], "family.deleted")

    def test_referenced_revision_blocks_permanent_prompt_delete(self):
        revision = self.create_prompt_history()
        with connect() as connection:
            with connection.cursor() as cursor:
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
                    VALUES (%s, 1, 'draft')
                    RETURNING id;
                    """,
                    (bundle_id,),
                )
                bundle_revision_id = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT r.id
                    FROM ai_prompt_revisions r
                    JOIN ai_prompt_variants v ON v.id = r.variant_id
                    JOIN ai_prompts p ON p.id = v.prompt_id
                    WHERE p.prompt_key = %s
                      AND v.variant_key = %s
                      AND r.revision_number = %s;
                    """,
                    (
                        revision["prompt_key"],
                        revision["variant_key"],
                        revision["revision_number"],
                    ),
                )
                revision_id = cursor.fetchone()[0]
                cursor.execute(
                    """
                    INSERT INTO ai_prompt_bundle_items (
                        bundle_revision_id,
                        role_key,
                        prompt_revision_id
                    )
                    VALUES (%s, %s, %s);
                    """,
                    (bundle_revision_id, "system", revision_id),
                )
            connection.commit()

        prompt_service.delete_prompt("prompt.deleted")
        response = self.client.post(
            "/deleted/prompts/prompt.deleted/permanent-delete",
            data={"confirm_key": "prompt.deleted"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("referenced by a Bundle item", response.text)
        deleted = prompt_service.get_prompt(
            "prompt.deleted",
            include_deleted=True,
        )
        self.assertIsNotNone(deleted["deleted_at"])

    def test_active_records_cannot_be_deleted_permanently(self):
        prompt_service.create_prompt(
            PromptCreate(
                prompt_key="prompt.active",
                display_name="Active prompt",
            )
        )

        with self.assertRaisesRegex(
            PromptAdminError,
            "soft-deleted first",
        ):
            deleted_record_service.permanently_delete_prompt(
                "prompt.active"
            )


if __name__ == "__main__":
    unittest.main()
