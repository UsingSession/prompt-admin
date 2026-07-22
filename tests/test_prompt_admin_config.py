import unittest

from pydantic import ValidationError

from config import Settings


class PromptAdminConfigTests(unittest.TestCase):
    def test_settings_load_valid_environment(self):
        settings = Settings.from_env(
            {
                "PROMPT_ADMIN_HOST": "127.0.0.1",
                "PROMPT_ADMIN_PORT": "9000",
                "POSTGRES_HOST": "database",
                "POSTGRES_PORT": "5433",
                "POSTGRES_DB": "prompt_admin",
                "POSTGRES_USER": "prompt_admin",
                "POSTGRES_PASSWORD": "secret",
            }
        )

        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 9000)
        self.assertEqual(settings.database_config["host"], "database")
        self.assertEqual(settings.database_config["port"], 5433)

    def test_settings_preserve_password_whitespace(self):
        settings = Settings.from_env(
            {"POSTGRES_PASSWORD": " leading-and-trailing "}
        )

        self.assertEqual(
            settings.postgres_password,
            " leading-and-trailing ",
        )

    def test_settings_reject_invalid_port(self):
        with self.assertRaises(ValidationError):
            Settings.from_env({"PROMPT_ADMIN_PORT": "70000"})

    def test_settings_reject_empty_database_user(self):
        with self.assertRaises(ValidationError):
            Settings.from_env({"POSTGRES_USER": " "})

    def test_settings_reject_empty_database_password(self):
        with self.assertRaises(ValidationError):
            Settings.from_env({"POSTGRES_PASSWORD": ""})


if __name__ == "__main__":
    unittest.main()
