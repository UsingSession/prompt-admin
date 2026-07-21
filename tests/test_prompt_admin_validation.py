import importlib.util
import sys
import unittest
from pathlib import Path


class PromptAdminValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prompt_admin_dir = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(prompt_admin_dir))

        module_path = prompt_admin_dir / "validation.py"
        spec = importlib.util.spec_from_file_location("prompt_admin_validation", module_path)
        cls.validation = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.validation)

    def test_validate_key_accepts_expected_chars(self):
        self.assertEqual(self.validation.validate_key("alpha_key-1.test"), "alpha_key-1.test")

    def test_validate_key_rejects_empty(self):
        with self.assertRaises(ValueError):
            self.validation.validate_key(" ")

    def test_validate_key_rejects_invalid_chars(self):
        with self.assertRaises(ValueError):
            self.validation.validate_key("bad/key")

    def test_normalize_hook_group_adds_prefix(self):
        self.assertEqual(self.validation.normalize_hook_group("global_rules"), "hook_global_rules")

    def test_normalize_hook_group_keeps_existing_prefix(self):
        self.assertEqual(self.validation.normalize_hook_group("hook_global_rules"), "hook_global_rules")

    def test_hook_group_suffix_removes_prefix(self):
        self.assertEqual(self.validation.hook_group_suffix("hook_global_rules"), "global_rules")

    def test_validate_prompt_text_detects_empty_prompt(self):
        warnings = self.validation.validate_prompt_text("")
        self.assertIn("Prompt is empty.", warnings)

    def test_validate_prompt_text_detects_hook_placeholder(self):
        warnings = self.validation.validate_prompt_text("Use #hook_global_rules. Output: text")
        self.assertIn("Prompt contains hook placeholders. Use compiled preview to verify them.", warnings)

    def test_validate_hook_text_detects_empty_hook(self):
        warnings = self.validation.validate_hook_text("")
        self.assertIn("Hook is empty.", warnings)


if __name__ == "__main__":
    unittest.main()
