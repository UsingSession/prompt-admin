import unittest

from errors import PromptAdminError
from services.compiler import (
    compile_resolved_prompt,
    parse_hook_groups,
)


class HookCompilerTests(unittest.TestCase):
    def test_parser_preserves_first_occurrence_and_deduplicates(self):
        raw_prompt = (
            "#hook_second.rules\n"
            "# ordinary heading\n"
            "#hook_first.rules\n"
            "#hook_second.rules"
        )

        self.assertEqual(
            parse_hook_groups(raw_prompt),
            ["hook_second.rules", "hook_first.rules"],
        )

    def test_parser_ignores_similar_invalid_forms(self):
        raw_prompt = "#hook_ #not_hook.rules hook_group # hook_group"

        self.assertEqual(parse_hook_groups(raw_prompt), [])

    def test_preview_compiles_all_occurrences_without_other_changes(self):
        raw_prompt = "Before\n#hook_global.rules\nMiddle #hook_global.rules\nAfter"
        hooks = [
            {
                "hook_key": "global.alpha",
                "revision_number": 2,
                "hook_group": "hook_global.rules",
                "hook_content": "Alpha",
                "priority": 10,
            },
            {
                "hook_key": "global.beta",
                "revision_number": 1,
                "hook_group": "hook_global.rules",
                "hook_content": "Beta",
                "priority": 20,
            },
        ]

        result = compile_resolved_prompt(raw_prompt, "preview", hooks)

        self.assertEqual(result["raw_prompt"], raw_prompt)
        self.assertEqual(
            result["compiled_prompt"],
            "Before\nAlpha\n\nBeta\nMiddle Alpha\n\nBeta\nAfter",
        )
        self.assertEqual(result["unresolved_groups"], [])
        self.assertEqual(len(result["resolved_hooks"]), 2)

    def test_preview_preserves_unresolved_tokens(self):
        raw_prompt = "Before #hook_missing.rules after"

        result = compile_resolved_prompt(raw_prompt, "preview", [])

        self.assertEqual(result["compiled_prompt"], raw_prompt)
        self.assertEqual(
            result["unresolved_groups"],
            ["hook_missing.rules"],
        )

    def test_strict_rejects_unresolved_groups(self):
        with self.assertRaises(PromptAdminError) as error:
            compile_resolved_prompt(
                "#hook_missing.rules",
                "strict",
                [],
            )

        self.assertEqual(error.exception.code, "unresolved_hook_groups")
        self.assertEqual(error.exception.status_code, 422)

    def test_prompt_without_placeholders_is_unchanged(self):
        raw_prompt = "No placeholders here.\nWhitespace stays.\n"

        result = compile_resolved_prompt(raw_prompt, "strict", [])

        self.assertEqual(result["compiled_prompt"], raw_prompt)
        self.assertEqual(result["detected_groups"], [])
        self.assertEqual(result["resolved_hooks"], [])


if __name__ == "__main__":
    unittest.main()
