import unittest

from fastapi.testclient import TestClient
from psycopg import sql

from app import create_app
from db import connect, init_database


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


class PromptManagementUiPostgresTests(unittest.TestCase):
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

    def test_html_create_redirect_detail_and_revision_compare_flow(self):
        family = self.client.post(
            "/families",
            data={
                "family_key": "family.ui",
                "display_name": "UI family",
                "description": "",
            },
            follow_redirects=False,
        )
        self.assertEqual(family.status_code, 303)

        prompt = self.client.post(
            "/prompts",
            data={
                "prompt_key": "prompt.ui",
                "display_name": "UI prompt",
                "description": "",
                "category": "ui",
                "family_key": "family.ui",
            },
            follow_redirects=False,
        )
        self.assertEqual(prompt.status_code, 303)

        variant = self.client.post(
            "/prompts/prompt.ui/variants",
            data={
                "variant_key": "baseline",
                "display_name": "Baseline",
                "description": "",
                "status": "available",
            },
            follow_redirects=False,
        )
        self.assertEqual(variant.status_code, 303)

        first_text = "  exact first line\n<script>alert(1)</script>\n"
        first = self.client.post(
            "/prompts/prompt.ui/variants/baseline/revisions",
            data={
                "system_prompt": first_text,
                "change_note": "Initial",
            },
            follow_redirects=False,
        )
        self.assertEqual(first.status_code, 303)

        second = self.client.post(
            "/prompts/prompt.ui/variants/baseline/revisions",
            data={
                "system_prompt": "  exact first line\nUpdated line\n",
                "change_note": "Update",
            },
            follow_redirects=False,
        )
        self.assertEqual(second.status_code, 303)

        detail = self.client.get(
            "/prompts/prompt.ui/variants/baseline/revisions/1"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertIn("&lt;script&gt;", detail.text)
        self.assertNotIn("<script>alert(1)</script>", detail.text)

        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM ai_prompt_revisions;"
                )
                count_before = cursor.fetchone()[0]

        comparison = self.client.get(
            "/prompts/prompt.ui/variants/baseline/compare"
            "?from_revision=1&to_revision=2"
        )
        self.assertEqual(comparison.status_code, 200)
        self.assertIn("Unified diff", comparison.text)
        self.assertIn("Side-by-side diff", comparison.text)

        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM ai_prompt_revisions;"
                )
                count_after = cursor.fetchone()[0]

        self.assertEqual(count_after, count_before)

    def test_archived_variant_blocks_revision_creation_from_ui(self):
        self.client.post(
            "/prompts",
            data={
                "prompt_key": "prompt.archived",
                "display_name": "Archived prompt",
                "description": "",
                "category": "",
                "family_key": "",
            },
        )
        self.client.post(
            "/prompts/prompt.archived/variants",
            data={
                "variant_key": "baseline",
                "display_name": "Baseline",
                "description": "",
                "status": "archived",
            },
        )

        response = self.client.post(
            "/prompts/prompt.archived/variants/baseline/revisions",
            data={
                "system_prompt": "Blocked",
                "change_note": "",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("Archived Variant", response.text)


if __name__ == "__main__":
    unittest.main()
