import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import create_app


NOW = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
FAMILY = {
    "family_key": "family.test",
    "display_name": "Test family",
    "description": "Family description",
    "created_at": NOW,
    "updated_at": NOW,
    "deleted_at": None,
}
PROMPT = {
    "prompt_key": "prompt.test",
    "display_name": "Test prompt",
    "description": "Prompt description",
    "category": "general",
    "family_key": "family.test",
    "created_at": NOW,
    "updated_at": NOW,
    "deleted_at": None,
}
VARIANT = {
    "prompt_key": "prompt.test",
    "variant_key": "baseline",
    "display_name": "Baseline",
    "description": "Baseline description",
    "status": "available",
    "created_at": NOW,
    "updated_at": NOW,
}
REVISION_1 = {
    "prompt_key": "prompt.test",
    "variant_key": "baseline",
    "revision_number": 1,
    "system_prompt": "First line\nOld line",
    "change_note": "Initial",
    "created_at": NOW,
}
REVISION_2 = {
    "prompt_key": "prompt.test",
    "variant_key": "baseline",
    "revision_number": 2,
    "system_prompt": "First line\nNew <script>alert(1)</script>",
    "change_note": "Update",
    "created_at": NOW,
}


class PromptManagementUiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            create_app(initialize_database=False),
            raise_server_exceptions=False,
        )
        self.addCleanup(self.client.close)

    def test_dashboard_has_active_navigation_and_only_current_features(self):
        with (
            patch(
                "ui.prompt_management.prompt_service.list_families",
                return_value=[FAMILY],
            ),
            patch(
                "ui.prompt_management.prompt_service.list_prompts",
                return_value=[PROMPT],
            ),
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('aria-current="page"', response.text)
        self.assertIn('href="/docs"', response.text)
        self.assertNotIn("Hooks", response.text)
        self.assertNotIn("Bundles", response.text)
        self.assertNotIn("Import / Export", response.text)

    def test_family_create_uses_post_redirect_get(self):
        with patch(
            "ui.prompt_management.prompt_service.create_family",
            return_value=FAMILY,
        ) as create_family:
            response = self.client.post(
                "/families",
                data={
                    "family_key": "family.test",
                    "display_name": "Test family",
                    "description": "",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 303)
        self.assertIn("/families/family.test", response.headers["location"])
        create_family.assert_called_once()

    def test_family_validation_preserves_safe_values(self):
        response = self.client.post(
            "/families",
            data={
                "family_key": " family.test",
                "display_name": "Visible value",
                "description": "Description",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Visible value", response.text)
        self.assertIn("surrounding whitespace", response.text)

    def test_family_detail_lists_associated_prompts(self):
        with (
            patch(
                "ui.prompt_management.prompt_service.get_family",
                return_value=FAMILY,
            ),
            patch(
                "ui.prompt_management.prompt_service.list_prompts",
                return_value=[PROMPT],
            ),
        ):
            response = self.client.get("/families/family.test")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Associated Prompts", response.text)
        self.assertIn("prompt.test", response.text)

    def test_prompt_metadata_form_has_no_prompt_text_field(self):
        with patch(
            "ui.prompt_management.prompt_service.list_families",
            return_value=[FAMILY],
        ):
            response = self.client.get("/prompts/new")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('name="system_prompt"', response.text)
        self.assertIn("Prompt text is not accepted here", response.text)

    def test_prompt_list_supports_filters_and_deleted_state(self):
        deleted_prompt = {**PROMPT, "deleted_at": NOW}
        with (
            patch(
                "ui.prompt_management.prompt_service.list_prompts",
                return_value=[deleted_prompt],
            ) as list_prompts,
            patch(
                "ui.prompt_management.prompt_service.list_families",
                return_value=[FAMILY],
            ),
        ):
            response = self.client.get(
                "/prompts?family_key=family.test"
                "&category=general&state=deleted"
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("badge-deleted", response.text)
        list_prompts.assert_any_call(
            family_key="family.test",
            category="general",
            include_deleted=True,
        )

    def test_variant_detail_has_no_delete_action(self):
        with (
            patch(
                "ui.prompt_management.prompt_service.get_prompt",
                return_value=PROMPT,
            ),
            patch(
                "ui.prompt_management.prompt_service.get_variant",
                return_value=VARIANT,
            ),
            patch(
                "ui.prompt_management.prompt_service.list_revisions",
                return_value=[REVISION_1],
            ),
        ):
            response = self.client.get(
                "/prompts/prompt.test/variants/baseline"
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Delete Variant", response.text)
        self.assertIn("Revision history", response.text)

    def test_archived_variant_hides_create_revision_action(self):
        archived = {**VARIANT, "status": "archived"}
        with (
            patch(
                "ui.prompt_management.prompt_service.get_prompt",
                return_value=PROMPT,
            ),
            patch(
                "ui.prompt_management.prompt_service.get_variant",
                return_value=archived,
            ),
            patch(
                "ui.prompt_management.prompt_service.list_revisions",
                return_value=[REVISION_1],
            ),
        ):
            response = self.client.get(
                "/prompts/prompt.test/variants/baseline"
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(">Create Revision<", response.text)
        self.assertIn("cannot be created", response.text)

    def test_revision_detail_escapes_prompt_text_and_is_immutable(self):
        dangerous_revision = {
            **REVISION_1,
            "system_prompt": "<script>alert(1)</script>",
        }
        with (
            patch(
                "ui.prompt_management.prompt_service.get_prompt",
                return_value=PROMPT,
            ),
            patch(
                "ui.prompt_management.prompt_service.get_variant",
                return_value=VARIANT,
            ),
            patch(
                "ui.prompt_management.prompt_service.get_revision",
                return_value=dangerous_revision,
            ),
        ):
            response = self.client.get(
                "/prompts/prompt.test/variants/baseline/revisions/1"
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("&lt;script&gt;", response.text)
        self.assertNotIn("<script>alert(1)</script>", response.text)
        self.assertIn("immutable", response.text)
        self.assertNotIn("Edit Revision", response.text)
        self.assertNotIn("Delete Revision", response.text)

    def test_revision_compare_renders_unified_and_side_by_side_diff(self):
        def get_revision(_, __, revision_number):
            return REVISION_1 if revision_number == 1 else REVISION_2

        with (
            patch(
                "ui.prompt_management.prompt_service.get_prompt",
                return_value=PROMPT,
            ),
            patch(
                "ui.prompt_management.prompt_service.get_variant",
                return_value=VARIANT,
            ),
            patch(
                "ui.prompt_management.prompt_service.list_revisions",
                return_value=[REVISION_1, REVISION_2],
            ),
            patch(
                "ui.prompt_management.prompt_service.get_revision",
                side_effect=get_revision,
            ),
        ):
            response = self.client.get(
                "/prompts/prompt.test/variants/baseline/compare"
                "?from_revision=1&to_revision=2"
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Unified diff", response.text)
        self.assertIn("Side-by-side diff", response.text)
        self.assertIn("&lt;script&gt;", response.text)
        self.assertNotIn("<script>alert(1)</script>", response.text)

    def test_compare_with_fewer_than_two_revisions_has_empty_state(self):
        with (
            patch(
                "ui.prompt_management.prompt_service.get_prompt",
                return_value=PROMPT,
            ),
            patch(
                "ui.prompt_management.prompt_service.get_variant",
                return_value=VARIANT,
            ),
            patch(
                "ui.prompt_management.prompt_service.list_revisions",
                return_value=[REVISION_1],
            ),
        ):
            response = self.client.get(
                "/prompts/prompt.test/variants/baseline/compare"
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("At least two Revisions", response.text)

    def test_cross_site_ui_post_returns_html_forbidden(self):
        response = self.client.post(
            "/families",
            data={},
            headers={"Origin": "https://example.com"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.headers["content-type"].split(";")[0],
            "text/html",
        )
        self.assertIn("Cross-site requests are not allowed", response.text)

    def test_ui_routes_are_not_added_to_openapi(self):
        document = self.client.get("/openapi.json").json()
        self.assertNotIn("/families", document["paths"])
        self.assertNotIn("/prompts", document["paths"])
        self.assertIn("/api/v1/families", document["paths"])


if __name__ == "__main__":
    unittest.main()
