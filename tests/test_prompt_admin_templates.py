import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class PromptAdminTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "psycopg" not in sys.modules:
            psycopg_stub = types.ModuleType("psycopg")
            psycopg_stub.connect = lambda **kwargs: None
            sys.modules["psycopg"] = psycopg_stub

        prompt_admin_dir = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(prompt_admin_dir))

        module_path = prompt_admin_dir / "render.py"
        spec = importlib.util.spec_from_file_location("prompt_admin_render", module_path)
        cls.render = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.render)

        export_path = prompt_admin_dir / "exporting.py"
        export_spec = importlib.util.spec_from_file_location("prompt_admin_exporting", export_path)
        cls.exporting = importlib.util.module_from_spec(export_spec)
        export_spec.loader.exec_module(cls.exporting)

    def test_render_index_uses_template_rows(self):
        prompt_summaries = [
            {
                "prompt_key": "alpha",
                "description": "Test prompt",
                "category": "starter",
                "is_active": True,
                "updated_at": "2026-01-01",
                "deleted_at": None,
                "line_count": 2,
                "char_count": 42,
            }
        ]

        html_output = self.render.render_index(prompt_summaries)

        self.assertIn("<title>Prompt Admin</title>", html_output)
        self.assertIn("<code>alpha</code>", html_output)
        self.assertIn('href="/edit?key=alpha"', html_output)
        self.assertIn('href="/download?key=alpha&format=md"', html_output)
        self.assertIn('href="/history?key=alpha"', html_output)
        self.assertIn("Active", html_output)
        self.assertIn("2 lines", html_output)
        self.assertIn("42 chars", html_output)
        self.assertNotIn("$rows_html", html_output)

    def test_render_form_escapes_values(self):
        html_output = self.render.render_form(
            {
                "prompt_key": 'a"b',
                "system_prompt": "<script>alert(1)</script>",
                "description": "bad <value>",
                "category": "starter",
                "is_active": True,
            },
            error="bad <value>",
        )

        self.assertIn("bad &lt;value&gt;", html_output)
        self.assertIn('value="a&quot;b" readonly required', html_output)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_output)
        self.assertIn('href="/download?key=a%22b&format=md"', html_output)
        self.assertIn('href="/download?key=a%22b&format=txt"', html_output)
        self.assertNotIn("$prompt_key", html_output)

    def test_build_download_payload_txt(self):
        content, content_type, filename = self.exporting.build_download_payload("alpha", "hello", "txt")

        self.assertEqual(content, "hello")
        self.assertEqual(content_type, "text/plain; charset=utf-8")
        self.assertEqual(filename, "alpha.txt")

    def test_build_download_payload_md(self):
        content, content_type, filename = self.exporting.build_download_payload(
            "alpha",
            "line 1\nline 2",
            "md",
        )

        self.assertIn("# Prompt Export", content)
        self.assertIn("**Prompt key:** `alpha`", content)
        self.assertIn("    line 1\n    line 2", content)
        self.assertEqual(content_type, "text/markdown; charset=utf-8")
        self.assertEqual(filename, "alpha.md")

    def test_build_download_payload_empty_prompt(self):
        txt_content, txt_content_type, txt_filename = self.exporting.build_download_payload("alpha", "", "txt")
        md_content, md_content_type, md_filename = self.exporting.build_download_payload("alpha", "", "md")

        self.assertEqual(txt_content, "")
        self.assertEqual(txt_content_type, "text/plain; charset=utf-8")
        self.assertEqual(txt_filename, "alpha.txt")
        self.assertIn("## System prompt\n\n    \n", md_content)
        self.assertEqual(md_content_type, "text/markdown; charset=utf-8")
        self.assertEqual(md_filename, "alpha.md")

    def test_build_download_payload_invalid_format(self):
        with self.assertRaises(ValueError):
            self.exporting.build_download_payload("alpha", "hello", "json")


if __name__ == "__main__":
    unittest.main()
