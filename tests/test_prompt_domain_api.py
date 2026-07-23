import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import create_app
from errors import PromptAdminError


NOW = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
FAMILY = {
    "family_key": "family.test",
    "display_name": "Test family",
    "description": "",
    "created_at": NOW,
    "updated_at": NOW,
    "deleted_at": None,
}
PROMPT = {
    "prompt_key": "prompt.test",
    "display_name": "Test prompt",
    "description": "",
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
    "description": "",
    "status": "available",
    "created_at": NOW,
    "updated_at": NOW,
}
REVISION = {
    "prompt_key": "prompt.test",
    "variant_key": "baseline",
    "revision_number": 1,
    "system_prompt": "System prompt",
    "change_note": "Initial revision",
    "created_at": NOW,
}


class PromptDomainApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            create_app(initialize_database=False),
            raise_server_exceptions=False,
        )
        self.addCleanup(self.client.close)

    def test_create_family_returns_schema_and_timestamp(self):
        with patch(
            "api.prompt_management.prompt_service.create_family",
            return_value=FAMILY,
        ):
            response = self.client.post(
                "/api/v1/families",
                json={
                    "family_key": "family.test",
                    "display_name": "Test family",
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["family_key"], "family.test")
        self.assertEqual(response.json()["created_at"], "2026-07-23T10:00:00Z")

    def test_prompt_create_rejects_system_prompt(self):
        response = self.client.post(
            "/api/v1/prompts",
            json={
                "prompt_key": "prompt.test",
                "display_name": "Test prompt",
                "system_prompt": "Not accepted",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["code"],
            "validation_failed",
        )

    def test_invalid_variant_status_has_stable_error_code(self):
        response = self.client.post(
            "/api/v1/prompts/prompt.test/variants",
            json={
                "variant_key": "baseline",
                "display_name": "Baseline",
                "status": "production",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["code"],
            "invalid_variant_status",
        )

    def test_domain_conflict_uses_stable_error_envelope(self):
        with patch(
            "api.prompt_management.prompt_service.create_family",
            side_effect=PromptAdminError(
                "family_key_conflict",
                "Stable key already exists.",
                409,
            ),
        ):
            response = self.client.post(
                "/api/v1/families",
                json={
                    "family_key": "family.test",
                    "display_name": "Test family",
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"],
            "family_key_conflict",
        )

    def test_create_revision_returns_immutable_revision_shape(self):
        with patch(
            "api.prompt_management.prompt_service.create_revision",
            return_value=REVISION,
        ):
            response = self.client.post(
                "/api/v1/prompts/prompt.test/variants/baseline/revisions",
                json={
                    "system_prompt": "System prompt",
                    "change_note": "Initial revision",
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["revision_number"], 1)
        self.assertEqual(response.json()["system_prompt"], "System prompt")

    def test_revision_update_and_delete_routes_do_not_exist(self):
        path = "/api/v1/prompts/prompt.test/variants/baseline/revisions/1"
        self.assertEqual(self.client.patch(path, json={}).status_code, 405)
        self.assertEqual(self.client.delete(path).status_code, 405)

    def test_openapi_registers_prompt_domain_routes(self):
        document = self.client.get("/openapi.json").json()
        paths = document["paths"]

        self.assertIn("/api/v1/families", paths)
        self.assertIn("/api/v1/prompts", paths)
        self.assertIn(
            "/api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions",
            paths,
        )
        revision_path = paths[
            "/api/v1/prompts/{prompt_key}/variants/"
            "{variant_key}/revisions/{revision}"
        ]
        self.assertEqual(set(revision_path), {"get"})

    def test_list_response_is_deterministic_boundary(self):
        with patch(
            "api.prompt_management.prompt_service.list_prompts",
            return_value=[PROMPT],
        ):
            response = self.client.get("/api/v1/prompts")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["items"][0]["prompt_key"], "prompt.test")

    def test_variant_response_schema(self):
        with patch(
            "api.prompt_management.prompt_service.get_variant",
            return_value=VARIANT,
        ):
            response = self.client.get(
                "/api/v1/prompts/prompt.test/variants/baseline"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "available")


if __name__ == "__main__":
    unittest.main()
