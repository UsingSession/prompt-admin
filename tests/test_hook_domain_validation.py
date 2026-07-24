import unittest

from pydantic import ValidationError

from schemas.hook import HookCreate, HookRevisionCreate, HookUpdate


class HookDomainValidationTests(unittest.TestCase):
    def test_hook_key_uses_stable_key_contract(self):
        for value in ("", " hook.test", "hook.test ", "hook.test_v2"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    HookCreate(
                        hook_key=value,
                        display_name="Test Hook",
                    )

    def test_hook_metadata_rejects_revision_fields(self):
        with self.assertRaises(ValidationError):
            HookCreate(
                hook_key="hook.test",
                display_name="Test Hook",
                hook_group="hook_global.rules",
            )

    def test_hook_update_rejects_key_and_empty_payload(self):
        with self.assertRaises(ValidationError):
            HookUpdate(hook_key="hook.changed")
        with self.assertRaises(ValidationError):
            HookUpdate()

    def test_valid_hook_revision_preserves_exact_content(self):
        content = "  Exact content\n"
        revision = HookRevisionCreate(
            hook_group="hook_global.rules",
            hook_content=content,
            priority=0,
        )

        self.assertEqual(revision.hook_content, content)
        self.assertEqual(revision.priority, 0)

    def test_invalid_hook_groups_are_rejected(self):
        invalid_groups = (
            "#hook_global.rules",
            " hook_global.rules",
            "hook_global.rules ",
            "global.rules",
            "hook_global rules",
            "hook_",
        )
        for value in invalid_groups:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    HookRevisionCreate(
                        hook_group=value,
                        hook_content="Content",
                    )

    def test_whitespace_content_and_negative_priority_are_rejected(self):
        with self.assertRaises(ValidationError):
            HookRevisionCreate(
                hook_group="hook_global.rules",
                hook_content=" \n ",
            )
        with self.assertRaises(ValidationError):
            HookRevisionCreate(
                hook_group="hook_global.rules",
                hook_content="Content",
                priority=-1,
            )


if __name__ == "__main__":
    unittest.main()
