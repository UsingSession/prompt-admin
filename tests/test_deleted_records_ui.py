import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import create_app


NOW = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
DELETED_FAMILY = {
    "family_key": "family.deleted",
    "display_name": "Deleted family",
    "description": "",
    "created_at": NOW,
    "updated_at": NOW,
    "deleted_at": NOW,
}
DELETED_PROMPT = {
    "prompt_key": "prompt.deleted",
    "display_name": "Deleted prompt",
    "description": "",
    "category": "general",
    "family_key": "family.deleted",
    "created_at": NOW,
    "updated_at": NOW,
    "deleted_at": NOW,
}


class DeletedRecordsUiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            create_app(initialize_database=False),
            raise_server_exceptions=False,
        )
        self.addCleanup(self.client.close)

    def test_deleted_records_page_lists_basket_and_navigation(self):
        def list_prompts(**kwargs):
            if kwargs.get("family_key") == "family.deleted":
                return [DELETED_PROMPT]
            return [DELETED_PROMPT]

        with (
            patch(
                "ui.deleted_records.prompt_service.list_families",
                return_value=[DELETED_FAMILY],
            ),
            patch(
                "ui.deleted_records.prompt_service.list_prompts",
                side_effect=list_prompts,
            ),
        ):
            response = self.client.get("/deleted")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Deleted Records", response.text)
        self.assertIn("family.deleted", response.text)
        self.assertIn("prompt.deleted", response.text)
        self.assertIn('aria-current="page"', response.text)
        self.assertIn("Delete permanently", response.text)
        self.assertNotIn('name="confirm_key"', response.text)

    def test_permanent_prompt_delete_uses_prg(self):
        with patch(
            "ui.deleted_records.deleted_record_service."
            "permanently_delete_prompt"
        ) as permanently_delete:
            response = self.client.post(
                "/deleted/prompts/prompt.deleted/permanent-delete",
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            response.headers["location"],
            "/deleted?status=prompt-permanently-deleted",
        )
        permanently_delete.assert_called_once_with("prompt.deleted")

    def test_permanent_family_delete_uses_prg(self):
        with patch(
            "ui.deleted_records.deleted_record_service."
            "permanently_delete_family"
        ) as permanently_delete:
            response = self.client.post(
                "/deleted/families/family.deleted/permanent-delete",
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 303)
        permanently_delete.assert_called_once_with("family.deleted")

    def test_cross_site_permanent_delete_is_rejected(self):
        with patch(
            "ui.deleted_records.deleted_record_service."
            "permanently_delete_prompt"
        ) as permanently_delete:
            response = self.client.post(
                "/deleted/prompts/prompt.deleted/permanent-delete",
                headers={"Origin": "https://example.com"},
            )

        self.assertEqual(response.status_code, 403)
        permanently_delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
