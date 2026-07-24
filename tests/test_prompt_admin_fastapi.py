import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import create_app


class PromptAdminFastApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            create_app(initialize_database=False),
            raise_server_exceptions=False,
        )
        self.addCleanup(self.client.close)

    def test_health_returns_ok_when_database_is_available(self):
        with patch("routes.db_health_check", return_value=True):
            response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "database": True},
        )

    def test_health_returns_503_when_database_is_unavailable(self):
        with patch("routes.db_health_check", side_effect=RuntimeError):
            response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "degraded", "database": False},
        )

    def test_responses_disable_unvalidated_cache_reuse(self):
        with patch("routes.db_health_check", return_value=True):
            response = self.client.get("/healthz")

        self.assertEqual(response.headers["cache-control"], "no-cache")

    def test_removed_compiled_api_returns_normal_404(self):
        response = self.client.get("/api/prompts/compiled")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_root_renders_prompt_admin_dashboard(self):
        with (
            patch(
                "ui.prompt_management.prompt_service.list_families",
                return_value=[],
            ),
            patch(
                "ui.prompt_management.prompt_service.list_prompts",
                return_value=[],
            ),
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Dashboard", response.text)
        self.assertEqual(
            response.headers["content-type"].split(";")[0],
            "text/html",
        )

    def test_cross_site_api_post_is_rejected(self):
        response = self.client.post(
            "/api/v1/families",
            json={},
            headers={"Origin": "https://example.com"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "forbidden")

    def test_localhost_subdomain_api_post_is_rejected(self):
        response = self.client.post(
            "/api/v1/families",
            json={},
            headers={"Origin": "http://localhost.evil.example"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "forbidden")

    def test_local_api_post_reaches_request_validation(self):
        response = self.client.post(
            "/api/v1/families",
            json={},
            headers={"Origin": "http://localhost:8090"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["code"],
            "validation_failed",
        )

    def test_removed_legacy_post_returns_normal_404(self):
        response = self.client.post(
            "/delete",
            data={"prompt_key": "assistant_rules"},
            headers={"Origin": "http://localhost:8090"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("404 Not Found", response.text)

    def test_unknown_api_route_returns_machine_readable_error(self):
        response = self.client.get("/api/unknown")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_unknown_ui_route_returns_html_error(self):
        response = self.client.get("/unknown")

        self.assertEqual(response.status_code, 404)
        self.assertIn("404 Not Found", response.text)
        self.assertEqual(
            response.headers["content-type"].split(";")[0],
            "text/html",
        )

    def test_static_files_are_mounted(self):
        response = self.client.get("/static/app.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn(":root", response.text)

    def test_lifespan_initializes_database(self):
        application = create_app()
        with patch("app.init_database") as initialize_database:
            with TestClient(application):
                pass
        initialize_database.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
