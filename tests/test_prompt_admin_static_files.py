import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class PromptAdminStaticFilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prompt_admin_dir = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(prompt_admin_dir))

        module_path = prompt_admin_dir / "static_files.py"
        spec = importlib.util.spec_from_file_location("prompt_admin_static_files", module_path)
        cls.static_files = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.static_files)

    def test_resolve_static_file_returns_content_type(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)
            css_file = static_dir / "app.css"
            css_file.write_text("body {}", encoding="utf-8")

            with patch.object(self.static_files, "STATIC_DIR", static_dir):
                body, content_type = self.static_files.resolve_static_file("app.css")

        self.assertEqual(body, b"body {}")
        self.assertEqual(content_type, "text/css")

    def test_resolve_static_file_blocks_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)
            with patch.object(self.static_files, "STATIC_DIR", static_dir):
                with self.assertRaises(ValueError):
                    self.static_files.resolve_static_file("../secret.txt")


if __name__ == "__main__":
    unittest.main()
