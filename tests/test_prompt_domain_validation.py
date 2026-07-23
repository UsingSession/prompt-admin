import unittest

from pydantic import ValidationError

from schemas.prompt import (
    FamilyCreate,
    FamilyUpdate,
    PromptCreate,
    PromptRevisionCreate,
    VariantCreate,
)


class PromptDomainValidationTests(unittest.TestCase):
    def test_rejects_whitespace_only_key(self):
        with self.assertRaises(ValidationError):
            FamilyCreate(family_key="   ", display_name="Family")

    def test_rejects_surrounding_key_whitespace_without_normalizing(self):
        with self.assertRaises(ValidationError):
            PromptCreate(prompt_key=" prompt.test ", display_name="Prompt")

    def test_rejects_revision_suffix_in_stable_key(self):
        with self.assertRaises(ValidationError):
            VariantCreate(
                variant_key="baseline_v2",
                display_name="Baseline",
            )

    def test_rejects_unexpected_fields(self):
        with self.assertRaises(ValidationError):
            PromptCreate(
                prompt_key="prompt.test",
                display_name="Prompt",
                system_prompt="Not allowed here",
            )

    def test_rejects_empty_patch(self):
        with self.assertRaises(ValidationError):
            FamilyUpdate()

    def test_rejects_null_non_nullable_patch_field(self):
        with self.assertRaises(ValidationError):
            FamilyUpdate(description=None)

    def test_preserves_prompt_text_exactly(self):
        data = PromptRevisionCreate(
            system_prompt="  exact prompt text\n",
            change_note="",
        )
        self.assertEqual(data.system_prompt, "  exact prompt text\n")

    def test_rejects_whitespace_only_prompt_text(self):
        with self.assertRaises(ValidationError):
            PromptRevisionCreate(system_prompt="\n  \t")


if __name__ == "__main__":
    unittest.main()
