import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient
from psycopg import sql

from app import create_app
from db import connect, init_database
from errors import PromptAdminError
from repositories import prompt_repository
from schemas.prompt import (
    FamilyCreate,
    FamilyUpdate,
    PromptCreate,
    PromptRevisionCreate,
    PromptUpdate,
    VariantCreate,
    VariantUpdate,
)
from services import prompt_service


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


class PromptDomainPostgresTests(unittest.TestCase):
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

    def create_family(self, key="family.test"):
        return prompt_service.create_family(
            FamilyCreate(
                family_key=key,
                display_name=f"Family {key}",
            )
        )

    def create_prompt(self, key="prompt.test", family_key=None):
        return prompt_service.create_prompt(
            PromptCreate(
                prompt_key=key,
                display_name=f"Prompt {key}",
                family_key=family_key,
            )
        )

    def create_variant(
        self,
        prompt_key="prompt.test",
        variant_key="baseline",
        status="available",
    ):
        return prompt_service.create_variant(
            prompt_key,
            VariantCreate(
                variant_key=variant_key,
                display_name=f"Variant {variant_key}",
                status=status,
            ),
        )

    def test_family_crud_soft_delete_restore_and_prompt_preservation(self):
        family = self.create_family()
        self.assertEqual(family["family_key"], "family.test")
        self.create_prompt(family_key="family.test")

        updated = prompt_service.update_family(
            "family.test",
            FamilyUpdate(
                display_name="Updated family",
                description="Updated description",
            ),
        )
        self.assertEqual(updated["display_name"], "Updated family")

        prompt_service.delete_family("family.test")
        self.assertEqual(prompt_service.list_families(), [])
        self.assertEqual(
            prompt_service.get_prompt("prompt.test")["family_key"],
            "family.test",
        )
        deleted = prompt_service.get_family(
            "family.test",
            include_deleted=True,
        )
        self.assertIsNotNone(deleted["deleted_at"])

        restored = prompt_service.restore_family("family.test")
        self.assertIsNone(restored["deleted_at"])

    def test_family_duplicate_and_invalid_assignment_are_stable_conflicts(self):
        self.create_family()
        with self.assertRaisesRegex(PromptAdminError, "already exists") as error:
            self.create_family()
        self.assertEqual(error.exception.code, "family_key_conflict")

        with self.assertRaises(PromptAdminError) as error:
            self.create_prompt(family_key="family.missing")
        self.assertEqual(error.exception.code, "invalid_reference")

        prompt_service.delete_family("family.test")
        with self.assertRaises(PromptAdminError) as error:
            self.create_prompt(
                key="prompt.deleted-family",
                family_key="family.test",
            )
        self.assertEqual(error.exception.code, "family_deleted")

    def test_prompt_crud_filters_soft_delete_and_restore(self):
        self.create_family()
        self.create_prompt(family_key="family.test")
        self.create_prompt(key="prompt.other")

        updated = prompt_service.update_prompt(
            "prompt.test",
            PromptUpdate(
                display_name="Updated prompt",
                category="general",
                family_key=None,
            ),
        )
        self.assertEqual(updated["display_name"], "Updated prompt")
        self.assertIsNone(updated["family_key"])

        filtered = prompt_service.list_prompts(category="general")
        self.assertEqual([item["prompt_key"] for item in filtered], ["prompt.test"])

        prompt_service.delete_prompt("prompt.test")
        self.assertEqual(
            [item["prompt_key"] for item in prompt_service.list_prompts()],
            ["prompt.other"],
        )
        deleted = prompt_service.get_prompt(
            "prompt.test",
            include_deleted=True,
        )
        self.assertIsNotNone(deleted["deleted_at"])
        restored = prompt_service.restore_prompt("prompt.test")
        self.assertIsNone(restored["deleted_at"])

    def test_prompt_duplicate_and_deleted_prompt_block_variant_creation(self):
        self.create_prompt()
        with self.assertRaises(PromptAdminError) as error:
            self.create_prompt()
        self.assertEqual(error.exception.code, "prompt_key_conflict")

        prompt_service.delete_prompt("prompt.test")
        with self.assertRaises(PromptAdminError) as error:
            self.create_variant()
        self.assertEqual(error.exception.code, "prompt_deleted")

    def test_variant_keys_are_scoped_to_prompt_and_status_is_mutable(self):
        self.create_prompt()
        self.create_prompt(key="prompt.other")
        self.create_variant()
        self.create_variant(prompt_key="prompt.other")

        with self.assertRaises(PromptAdminError) as error:
            self.create_variant()
        self.assertEqual(error.exception.code, "variant_key_conflict")

        archived = prompt_service.update_variant(
            "prompt.test",
            "baseline",
            VariantUpdate(status="archived"),
        )
        self.assertEqual(archived["status"], "archived")
        available = prompt_service.update_variant(
            "prompt.test",
            "baseline",
            VariantUpdate(status="available"),
        )
        self.assertEqual(available["status"], "available")

    def test_revision_numbers_history_and_exact_text(self):
        self.create_prompt()
        self.create_variant()
        first_text = "  first exact prompt\n"
        first = prompt_service.create_revision(
            "prompt.test",
            "baseline",
            PromptRevisionCreate(system_prompt=first_text),
        )
        second = prompt_service.create_revision(
            "prompt.test",
            "baseline",
            PromptRevisionCreate(
                system_prompt="Second prompt",
                change_note="Second revision",
            ),
        )

        self.assertEqual(first["revision_number"], 1)
        self.assertEqual(first["system_prompt"], first_text)
        self.assertEqual(second["revision_number"], 2)
        history = prompt_service.list_revisions("prompt.test", "baseline")
        self.assertEqual(
            [item["revision_number"] for item in history],
            [1, 2],
        )

    def test_revision_creation_rejects_missing_deleted_and_archived_state(self):
        with self.assertRaises(PromptAdminError) as error:
            prompt_service.create_revision(
                "prompt.missing",
                "baseline",
                PromptRevisionCreate(system_prompt="Prompt"),
            )
        self.assertEqual(error.exception.code, "prompt_not_found")

        self.create_prompt()
        with self.assertRaises(PromptAdminError) as error:
            prompt_service.create_revision(
                "prompt.test",
                "missing",
                PromptRevisionCreate(system_prompt="Prompt"),
            )
        self.assertEqual(error.exception.code, "variant_not_found")

        self.create_variant(status="archived")
        with self.assertRaises(PromptAdminError) as error:
            prompt_service.create_revision(
                "prompt.test",
                "baseline",
                PromptRevisionCreate(system_prompt="Prompt"),
            )
        self.assertEqual(error.exception.code, "variant_archived")

        prompt_service.update_variant(
            "prompt.test",
            "baseline",
            VariantUpdate(status="available"),
        )
        prompt_service.delete_prompt("prompt.test")
        with self.assertRaises(PromptAdminError) as error:
            prompt_service.create_revision(
                "prompt.test",
                "baseline",
                PromptRevisionCreate(system_prompt="Prompt"),
            )
        self.assertEqual(error.exception.code, "prompt_deleted")

    def test_revision_transaction_rolls_back_after_insert_failure(self):
        self.create_prompt()
        self.create_variant()

        with patch(
            "services.prompt_service.repository.get_revision_by_id",
            side_effect=RuntimeError("after insert"),
        ):
            with self.assertRaises(RuntimeError):
                prompt_service.create_revision(
                    "prompt.test",
                    "baseline",
                    PromptRevisionCreate(system_prompt="Prompt"),
                )

        self.assertEqual(
            prompt_service.list_revisions("prompt.test", "baseline"),
            [],
        )

    def test_concurrent_revision_creation_is_sequential(self):
        self.create_prompt()
        self.create_variant()
        barrier = threading.Barrier(2)

        def create_revision(index):
            barrier.wait(timeout=5)
            return prompt_service.create_revision(
                "prompt.test",
                "baseline",
                PromptRevisionCreate(system_prompt=f"Prompt {index}"),
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create_revision, index) for index in range(2)]
            results = [future.result(timeout=15) for future in futures]

        self.assertEqual(
            sorted(item["revision_number"] for item in results),
            [1, 2],
        )

    def test_revision_repository_exposes_no_mutation_methods(self):
        self.assertFalse(hasattr(prompt_repository, "update_revision"))
        self.assertFalse(hasattr(prompt_repository, "delete_revision"))

    def test_real_api_success_conflict_not_found_and_immutability(self):
        created = self.client.post(
            "/api/v1/families",
            json={
                "family_key": "family.api",
                "display_name": "API family",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertIn("created_at", created.json())

        duplicate = self.client.post(
            "/api/v1/families",
            json={
                "family_key": "family.api",
                "display_name": "Duplicate",
            },
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(
            duplicate.json()["error"]["code"],
            "family_key_conflict",
        )

        missing = self.client.get("/api/v1/prompts/prompt.missing")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(
            missing.json()["error"]["code"],
            "prompt_not_found",
        )

        revision_path = (
            "/api/v1/prompts/prompt.test/variants/baseline/revisions/1"
        )
        self.assertEqual(self.client.patch(revision_path, json={}).status_code, 405)
        self.assertEqual(self.client.delete(revision_path).status_code, 405)


if __name__ == "__main__":
    unittest.main()
