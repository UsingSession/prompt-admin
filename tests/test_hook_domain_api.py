import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import create_app


NOW = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)
HOOK = {
    "hook_key": "global.rules",
    "display_name": "Global rules",
    "description": "",
    "category": "global",
    "created_at": NOW,
    "updated_at": NOW,
    "deleted_at": None,
}
REVISION = {
    "hook_key": "global.rules",
    "revision_number": 1,
    "hook_group": "hook_global.rules",
    "hook_content": "Rule content",
    "priority": 100,
    "is_enabled": True,
    "change_note": "Initial",
    "created_at": NOW,
}
PREVIEW = {
    "mode": "preview",
    "raw_prompt": "Before #hook_global.rules",
    "compiled_prompt": "Before Rule content",
    "detected_groups": ["hook_global.rules"],
    "resolved_hooks": [
        {
            "hook_key": "global.rules",
            "revision_number": 1,
            "hook_group": "hook_global.rules",
            "priority": 100,
        }
    ],
    "unresolved_groups": [],
}


class HookDomainApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            create_app(initialize_database=False),
            raise_server_exceptions=False,
        )
        self.addCleanup(self.client.close)

    def test_create_hook_returns_strict_response_schema(self):
        with patch(
            "api.hook_management.hook_service.create_hook",
            return_value=HOOK,
        ):
            response = self.client.post(
                "/api/v1/hooks",
                json={
                    "hook_key": "global.rules",
                    "display_name": "Global rules",
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["hook_key"], "global.rules")
        self.assertEqual(response.json()["created_at"], "2026-07-24T10:00:00Z")

    def test_hook_metadata_rejects_revision_fields(self):
        response = self.client.post(
            "/api/v1/hooks",
            json={
                "hook_key": "global.rules",
                "display_name": "Global rules",
                "hook_content": "Not accepted",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["code"],
            "validation_failed",
        )

    def test_revision_validation_uses_stable_codes(self):
        invalid_group = self.client.post(
            "/api/v1/hooks/global.rules/revisions",
            json={
                "hook_group": "#hook_global.rules",
                "hook_content": "Content",
            },
        )
        invalid_priority = self.client.post(
            "/api/v1/hooks/global.rules/revisions",
            json={
                "hook_group": "hook_global.rules",
                "hook_content": "Content",
                "priority": -1,
            },
        )

        self.assertEqual(invalid_group.status_code, 422)
        self.assertEqual(
            invalid_group.json()["error"]["code"],
            "invalid_hook_group",
        )
        self.assertEqual(invalid_priority.status_code, 422)
        self.assertEqual(
            invalid_priority.json()["error"]["code"],
            "invalid_hook_priority",
        )

    def test_hook_revision_routes_are_immutable(self):
        path = "/api/v1/hooks/global.rules/revisions/1"

        self.assertEqual(self.client.patch(path, json={}).status_code, 405)
        self.assertEqual(self.client.put(path, json={}).status_code, 405)
        self.assertEqual(self.client.delete(path).status_code, 405)

    def test_compiled_preview_returns_current_hook_metadata(self):
        path = (
            "/api/v1/prompts/prompt.test/variants/baseline/"
            "revisions/1/compiled-preview"
        )
        with patch(
            "api.prompt_compilation.compiler.preview_prompt_revision",
            return_value=PREVIEW,
        ):
            response = self.client.get(path)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "preview")
        self.assertEqual(
            response.json()["resolved_hooks"][0]["hook_key"],
            "global.rules",
        )

    def test_openapi_registers_only_supported_hook_mutations(self):
        paths = self.client.get("/openapi.json").json()["paths"]

        self.assertEqual(set(paths["/api/v1/hooks"]), {"get", "post"})
        revision_path = paths[
            "/api/v1/hooks/{hook_key}/revisions/{revision}"
        ]
        self.assertEqual(set(revision_path), {"get"})
        self.assertIn(
            "/api/v1/prompts/{prompt_key}/variants/{variant_key}/"
            "revisions/{revision}/compiled-preview",
            paths,
        )

    def test_hook_ui_remains_unregistered(self):
        response = self.client.get("/hooks")

        self.assertEqual(response.status_code, 404)
        self.assertIn("text/html", response.headers["content-type"])

    def test_exact_origin_protection_applies_to_hook_writes(self):
        response = self.client.post(
            "/api/v1/hooks",
            headers={"Origin": "http://localhost.evil.example"},
            json={
                "hook_key": "global.rules",
                "display_name": "Global rules",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.headers["Cache-Control"], "no-cache")

    def test_revision_response_schema(self):
        with patch(
            "api.hook_management.hook_service.get_revision",
            return_value=REVISION,
        ):
            response = self.client.get(
                "/api/v1/hooks/global.rules/revisions/1"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revision_number"], 1)


if __name__ == "__main__":
    unittest.main()
