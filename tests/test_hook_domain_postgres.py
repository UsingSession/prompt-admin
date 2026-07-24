import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient
from psycopg import sql

from app import create_app
from db import connect, init_database
from errors import PromptAdminError
from repositories import hook_repository
from schemas.hook import HookCreate, HookRevisionCreate, HookUpdate
from schemas.prompt import PromptCreate, PromptRevisionCreate, VariantCreate
from services import compiler, hook_service, prompt_service


DROP_ORDER = (
    "ai_compiled_bundle_artifacts",
    "ai_prompt_bundle_items",
    "ai_prompt_bundle_revisions",
    "ai_prompt_bundles",
    "ai_hook_revisions",
    "ai_hooks",
    "ai_prompt_revisions",
    "ai_prompt_variants",
    "ai_prompts",
    "ai_prompt_families",
    "prompt_admin_migrations",
)


class HookDomainPostgresTests(unittest.TestCase):
    def setUp(self):
        self.reset_database()
        init_database()
        self.client = TestClient(
            create_app(initialize_database=False),
            raise_server_exceptions=False,
        )
        self.addCleanup(self.client.close)

    def tearDown(self):
        self.reset_database()

    def reset_database(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                for table_name in DROP_ORDER:
                    cursor.execute(
                        sql.SQL("DROP TABLE IF EXISTS {} CASCADE;").format(
                            sql.Identifier(table_name)
                        )
                    )
            connection.commit()

    def create_hook(
        self,
        key="global.rules",
        category="global",
    ):
        return hook_service.create_hook(
            HookCreate(
                hook_key=key,
                display_name=f"Hook {key}",
                category=category,
            )
        )

    def create_hook_revision(
        self,
        key="global.rules",
        group="hook_global.rules",
        content="Rule content",
        priority=100,
        is_enabled=True,
    ):
        return hook_service.create_revision(
            key,
            HookRevisionCreate(
                hook_group=group,
                hook_content=content,
                priority=priority,
                is_enabled=is_enabled,
            ),
        )

    def create_prompt_revision(self, system_prompt):
        prompt_service.create_prompt(
            PromptCreate(
                prompt_key="prompt.test",
                display_name="Prompt test",
            )
        )
        prompt_service.create_variant(
            "prompt.test",
            VariantCreate(
                variant_key="baseline",
                display_name="Baseline",
                status="available",
            ),
        )
        return prompt_service.create_revision(
            "prompt.test",
            "baseline",
            PromptRevisionCreate(system_prompt=system_prompt),
        )

    def test_hook_metadata_lifecycle_filters_and_reserved_key(self):
        self.create_hook()
        self.create_hook(key="image.rules", category="image")

        updated = hook_service.update_hook(
            "global.rules",
            HookUpdate(
                display_name="Updated global rules",
                description="Updated",
            ),
        )
        self.assertEqual(updated["display_name"], "Updated global rules")
        self.assertEqual(
            [item["hook_key"] for item in hook_service.list_hooks("image")],
            ["image.rules"],
        )

        hook_service.delete_hook("global.rules")
        self.assertEqual(
            [item["hook_key"] for item in hook_service.list_hooks()],
            ["image.rules"],
        )
        deleted = hook_service.get_hook(
            "global.rules",
            include_deleted=True,
        )
        self.assertIsNotNone(deleted["deleted_at"])
        with self.assertRaises(PromptAdminError) as error:
            self.create_hook()
        self.assertEqual(error.exception.code, "hook_key_conflict")

        restored = hook_service.restore_hook("global.rules")
        self.assertIsNone(restored["deleted_at"])

    def test_revision_history_exact_content_and_deleted_hook_block(self):
        self.create_hook()
        exact_content = "  exact content\n"
        first = self.create_hook_revision(content=exact_content, priority=0)
        second = self.create_hook_revision(
            content="Disabled",
            is_enabled=False,
        )

        self.assertEqual(first["revision_number"], 1)
        self.assertEqual(first["hook_content"], exact_content)
        self.assertEqual(second["revision_number"], 2)
        self.assertFalse(second["is_enabled"])
        self.assertEqual(
            [
                item["revision_number"]
                for item in hook_service.list_revisions("global.rules")
            ],
            [1, 2],
        )

        hook_service.delete_hook("global.rules")
        with self.assertRaises(PromptAdminError) as error:
            self.create_hook_revision(content="Blocked")
        self.assertEqual(error.exception.code, "hook_deleted")

    def test_revision_transaction_rolls_back_after_insert_failure(self):
        self.create_hook()

        with patch(
            "services.hook_service.repository.get_revision_by_id",
            side_effect=RuntimeError("after insert"),
        ):
            with self.assertRaises(RuntimeError):
                self.create_hook_revision()

        self.assertEqual(hook_service.list_revisions("global.rules"), [])

    def test_concurrent_revision_creation_is_sequential(self):
        self.create_hook()
        barrier = threading.Barrier(2)

        def create_revision(index):
            barrier.wait(timeout=5)
            return self.create_hook_revision(content=f"Rule {index}")

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create_revision, index) for index in range(2)]
            results = [future.result(timeout=15) for future in futures]

        self.assertEqual(
            sorted(item["revision_number"] for item in results),
            [1, 2],
        )

    def test_effective_revision_never_falls_back_and_restore_uses_latest(self):
        self.create_hook()
        self.create_hook_revision(content="Enabled old")
        self.create_hook_revision(content="Disabled latest", is_enabled=False)
        self.create_prompt_revision("#hook_global.rules")

        disabled = compiler.preview_prompt_revision(
            "prompt.test",
            "baseline",
            1,
        )
        self.assertEqual(
            disabled["unresolved_groups"],
            ["hook_global.rules"],
        )
        self.assertEqual(
            disabled["compiled_prompt"],
            "#hook_global.rules",
        )

        self.create_hook_revision(content="Enabled latest")
        enabled = compiler.preview_prompt_revision(
            "prompt.test",
            "baseline",
            1,
        )
        self.assertEqual(enabled["compiled_prompt"], "Enabled latest")

        hook_service.delete_hook("global.rules")
        deleted = compiler.preview_prompt_revision(
            "prompt.test",
            "baseline",
            1,
        )
        self.assertEqual(deleted["unresolved_groups"], ["hook_global.rules"])

        hook_service.restore_hook("global.rules")
        restored = compiler.preview_prompt_revision(
            "prompt.test",
            "baseline",
            1,
        )
        self.assertEqual(restored["compiled_prompt"], "Enabled latest")

    def test_resolution_order_is_priority_then_key_and_uses_separator(self):
        self.create_hook(key="rules.beta")
        self.create_hook_revision(
            key="rules.beta",
            content="Beta",
            priority=10,
        )
        self.create_hook(key="rules.alpha")
        self.create_hook_revision(
            key="rules.alpha",
            content="Alpha",
            priority=10,
        )
        self.create_hook(key="rules.first")
        self.create_hook_revision(
            key="rules.first",
            content="First",
            priority=1,
        )
        self.create_prompt_revision("Before\n#hook_global.rules\nAfter")

        result = compiler.preview_prompt_revision(
            "prompt.test",
            "baseline",
            1,
        )

        self.assertEqual(
            result["compiled_prompt"],
            "Before\nFirst\n\nAlpha\n\nBeta\nAfter",
        )
        self.assertEqual(
            [item["hook_key"] for item in result["resolved_hooks"]],
            ["rules.first", "rules.alpha", "rules.beta"],
        )

    def test_preview_endpoint_preserves_unresolved_and_performs_no_writes(self):
        self.create_prompt_revision(
            "Resolved: #hook_global.rules\nMissing: #hook_missing.rules"
        )
        self.create_hook()
        self.create_hook_revision(content="Current rules")
        revision_count_before = len(
            prompt_service.list_revisions("prompt.test", "baseline")
        )
        hook_count_before = len(hook_service.list_revisions("global.rules"))

        response = self.client.get(
            "/api/v1/prompts/prompt.test/variants/baseline/"
            "revisions/1/compiled-preview"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["unresolved_groups"],
            ["hook_missing.rules"],
        )
        self.assertIn("#hook_missing.rules", response.json()["compiled_prompt"])
        self.assertEqual(
            len(prompt_service.list_revisions("prompt.test", "baseline")),
            revision_count_before,
        )
        self.assertEqual(
            len(hook_service.list_revisions("global.rules")),
            hook_count_before,
        )

    def test_strict_mode_uses_stable_error_and_repository_is_immutable(self):
        self.create_prompt_revision("#hook_missing.rules")

        with connect() as connection:
            with connection.cursor() as cursor:
                with self.assertRaises(PromptAdminError) as error:
                    compiler.compile_with_cursor(
                        cursor,
                        "#hook_missing.rules",
                        "strict",
                    )
        self.assertEqual(error.exception.code, "unresolved_hook_groups")
        self.assertFalse(hasattr(hook_repository, "update_revision"))
        self.assertFalse(hasattr(hook_repository, "delete_revision"))


if __name__ == "__main__":
    unittest.main()
