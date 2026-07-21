import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class PromptAdminCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "psycopg" not in sys.modules:
            psycopg_stub = types.ModuleType("psycopg")
            psycopg_stub.connect = lambda **kwargs: None
            sys.modules["psycopg"] = psycopg_stub

        prompt_admin_dir = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(prompt_admin_dir))

        module_path = prompt_admin_dir / "compiler.py"
        spec = importlib.util.spec_from_file_location("prompt_admin_compiler", module_path)
        cls.compiler = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.compiler)

    def test_find_hook_groups(self):
        groups = self.compiler.find_hook_groups("A\n#hook_global_rules\n#hook_rag_rules")
        self.assertEqual(groups, ["hook_global_rules", "hook_rag_rules"])

    def test_compile_prompt_text_replaces_known_hook(self):
        hooks = [
            {
                "hook_key": "hook_global_rules-simple_english",
                "hook_group": "hook_global_rules",
                "hook_content": "Use simple English.",
            }
        ]
        with patch.object(self.compiler, "list_active_hooks_by_group", return_value=hooks):
            result = self.compiler.compile_prompt_text("A\n#hook_global_rules\nB")

        self.assertIn("Use simple English.", result["compiled_prompt"])
        self.assertEqual(result["detected_groups"], ["hook_global_rules"])
        self.assertEqual(result["unresolved_groups"], [])


if __name__ == "__main__":
    unittest.main()
