import importlib.util
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path


class PromptAdminHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "psycopg" not in sys.modules:
            psycopg_stub = types.ModuleType("psycopg")
            psycopg_stub.connect = lambda **kwargs: None
            sys.modules["psycopg"] = psycopg_stub

        prompt_admin_dir = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(prompt_admin_dir))

        module_path = prompt_admin_dir / "handlers.py"
        spec = importlib.util.spec_from_file_location("prompt_admin_handlers", module_path)
        cls.handlers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.handlers)

    def test_prompt_keys_from_query_supports_repeated_keys(self):
        keys = self.handlers.prompt_keys_from_query({"key": ["script_writer", "tag_retrieval_planner"]})

        self.assertEqual(keys, ["script_writer", "tag_retrieval_planner"])

    def test_prompt_keys_from_query_supports_comma_separated_keys(self):
        keys = self.handlers.prompt_keys_from_query({"keys": ["script_writer, tag_retrieval_planner"]})

        self.assertEqual(keys, ["script_writer", "tag_retrieval_planner"])

    def test_prompt_keys_from_query_supports_mixed_key_formats(self):
        keys = self.handlers.prompt_keys_from_query(
            {
                "key": ["script_writer"],
                "keys": ["tag_retrieval_planner, character_detail_designer"],
            }
        )

        self.assertEqual(keys, ["script_writer", "tag_retrieval_planner", "character_detail_designer"])

    def test_prompt_keys_from_query_deduplicates_keys(self):
        keys = self.handlers.prompt_keys_from_query(
            {
                "key": ["script_writer"],
                "keys": ["script_writer,tag_retrieval_planner"],
            }
        )

        self.assertEqual(keys, ["script_writer", "tag_retrieval_planner"])

    def test_missing_prompt_keys_returns_requested_keys_not_returned(self):
        missing = self.handlers.missing_prompt_keys(
            ["script_writer", "tag_retrieval_planner", "missing_prompt"],
            [
                {"prompt_key": "script_writer"},
                {"prompt_key": "tag_retrieval_planner"},
            ],
        )

        self.assertEqual(missing, ["missing_prompt"])

    def test_missing_prompt_keys_skips_prompt_scan_without_requested_keys(self):
        missing = self.handlers.missing_prompt_keys([], [object()])

        self.assertEqual(missing, [])

    def test_handle_compiled_prompts_api_requires_filter(self):
        class Stub:
            def send_json(self, payload, status):
                self.payload = payload
                self.status = status
                return payload, status

        stub = Stub()
        payload, status = self.handlers.Handler.handle_compiled_prompts_api(stub, {})
        self.assertEqual(status, self.handlers.HTTPStatus.BAD_REQUEST)
        self.assertEqual(payload["error"], "Provide category, key, or keys query parameter.")

    def test_handle_compiled_prompts_api_returns_compiled_prompts_by_category(self):
        calls = {}

        def fake_list_active_prompts(**kwargs):
            calls.update(kwargs)
            return [
                {
                    "prompt_key": "script_writer",
                    "system_prompt": "raw",
                    "description": "",
                    "category": "image_generation",
                    "is_active": True,
                    "updated_at": None,
                    "deleted_at": None,
                }
            ]

        class Stub:
            def send_json(self, payload, status=200):
                self.payload = payload
                self.status = status
                return payload, status

            def compiled_prompt_payload(self, prompt):
                return {"prompt_key": prompt["prompt_key"], "compiled_prompt": "compiled"}

        original = self.handlers.list_active_prompts
        self.handlers.list_active_prompts = fake_list_active_prompts
        try:
            stub = Stub()
            payload, status = self.handlers.Handler.handle_compiled_prompts_api(stub, {"category": ["image_generation"]})
        finally:
            self.handlers.list_active_prompts = original

        self.assertEqual(status, self.handlers.HTTPStatus.OK)
        self.assertEqual(calls, {"category": "image_generation", "prompt_keys": []})
        self.assertEqual(payload["category"], "image_generation")
        self.assertEqual(payload["keys"], [])
        self.assertEqual(payload["missing_keys"], [])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["prompts"], [{"prompt_key": "script_writer", "compiled_prompt": "compiled"}])

    def test_handle_compiled_prompts_api_propagates_multiple_keys(self):
        calls = {}

        def fake_list_active_prompts(**kwargs):
            calls.update(kwargs)
            return []

        class Stub:
            def send_json(self, payload, status=200):
                return payload, status

            def compiled_prompt_payload(self, prompt):
                return prompt

        original = self.handlers.list_active_prompts
        self.handlers.list_active_prompts = fake_list_active_prompts
        try:
            payload, status = self.handlers.Handler.handle_compiled_prompts_api(
                Stub(),
                {"keys": ["script_writer,tag_retrieval_planner"]},
            )
        finally:
            self.handlers.list_active_prompts = original

        self.assertEqual(status, self.handlers.HTTPStatus.OK)
        self.assertEqual(
            calls,
            {
                "category": "",
                "prompt_keys": ["script_writer", "tag_retrieval_planner"],
            },
        )
        self.assertEqual(payload["keys"], ["script_writer", "tag_retrieval_planner"])
        self.assertEqual(payload["missing_keys"], ["script_writer", "tag_retrieval_planner"])
        self.assertEqual(payload["prompts"], [])

    def test_handle_compiled_prompts_api_reports_missing_keys(self):
        def fake_list_active_prompts(**kwargs):
            return [
                {
                    "prompt_key": "script_writer",
                    "system_prompt": "raw",
                    "description": "",
                    "category": "image_generation",
                    "is_active": True,
                    "updated_at": None,
                    "deleted_at": None,
                }
            ]

        class Stub:
            def send_json(self, payload, status=200):
                return payload, status

            def compiled_prompt_payload(self, prompt):
                return {"prompt_key": prompt["prompt_key"]}

        original = self.handlers.list_active_prompts
        self.handlers.list_active_prompts = fake_list_active_prompts
        try:
            payload, status = self.handlers.Handler.handle_compiled_prompts_api(
                Stub(),
                {"keys": ["script_writer,missing_prompt"]},
            )
        finally:
            self.handlers.list_active_prompts = original

        self.assertEqual(status, self.handlers.HTTPStatus.OK)
        self.assertEqual(payload["keys"], ["script_writer", "missing_prompt"])
        self.assertEqual(payload["missing_keys"], ["missing_prompt"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["prompts"], [{"prompt_key": "script_writer"}])

    def test_compiled_prompt_payload_returns_expected_json_shape(self):
        def fake_compile_prompt_text(system_prompt):
            return {
                "raw_prompt": system_prompt,
                "compiled_prompt": "compiled prompt",
                "detected_groups": ["hook_global_rules"],
                "resolved_hooks": [
                    {
                        "hook_key": "hook_global_rules-user_intent",
                        "hook_group": "hook_global_rules",
                        "description": "Preserve intent",
                        "category": "global",
                        "priority": 10,
                        "is_active": True,
                    }
                ],
                "unresolved_groups": [],
            }

        original = self.handlers.compile_prompt_text
        self.handlers.compile_prompt_text = fake_compile_prompt_text
        try:
            payload = self.handlers.Handler.compiled_prompt_payload(
                object(),
                {
                    "prompt_key": "script_writer",
                    "system_prompt": "raw prompt",
                    "description": "Writes scripts",
                    "category": "image_generation",
                    "is_active": True,
                    "updated_at": datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc),
                },
            )
        finally:
            self.handlers.compile_prompt_text = original

        self.assertEqual(payload["prompt_key"], "script_writer")
        self.assertEqual(payload["category"], "image_generation")
        self.assertEqual(payload["raw_prompt"], "raw prompt")
        self.assertEqual(payload["compiled_prompt"], "compiled prompt")
        self.assertEqual(payload["updated_at"], "2026-07-01T09:00:00+00:00")
        self.assertEqual(payload["detected_groups"], ["hook_global_rules"])
        self.assertEqual(payload["resolved_hooks"][0]["priority"], 10)
        self.assertEqual(payload["unresolved_groups"], [])

    def test_safe_hook_from_form_preserves_invalid_hook_group_without_validation(self):
        hook = self.handlers.Handler.safe_hook_from_form(
            object(),
            {
                "hook_key": ["hook_global_rules-user_intent"],
                "hook_group": ["invalid hook group"],
                "hook_content": ["content"],
                "description": ["description"],
                "category": ["global"],
                "priority": ["10"],
                "is_active": ["1"],
            },
        )

        self.assertEqual(hook["hook_group"], "invalid hook group")
        self.assertEqual(hook["hook_content"], "content")
        self.assertTrue(hook["is_active"])

    def test_do_get_returns_json_bad_request_for_api_validation_error(self):
        class Stub:
            path = "/api/prompts/compiled?key=invalid%20key"

            def send_json(self, payload, status):
                return payload, status

        payload, status = self.handlers.Handler.do_GET(Stub())

        self.assertEqual(status, self.handlers.HTTPStatus.BAD_REQUEST)
        self.assertIn("error", payload)
        self.assertNotEqual(payload["error"], "Request failed.")

    def test_do_get_returns_html_bad_request_for_validation_error(self):
        class Stub:
            path = "/download?key=script_writer&format=json"

            def send_html(self, content, status):
                return content, status

        def fake_get_prompt(prompt_key):
            return {
                "prompt_key": prompt_key,
                "system_prompt": "raw prompt",
            }

        original = self.handlers.get_prompt
        self.handlers.get_prompt = fake_get_prompt
        try:
            content, status = self.handlers.Handler.do_GET(Stub())
        finally:
            self.handlers.get_prompt = original

        self.assertEqual(status, self.handlers.HTTPStatus.BAD_REQUEST)
        self.assertIn("Bad request", content)

    def test_send_json_uses_strict_json_encoding(self):
        class Stub:
            def send_bytes(self, body, content_type, status):
                return body, content_type, status

        with self.assertRaises(TypeError):
            self.handlers.Handler.send_json(Stub(), {"value": object()})


if __name__ == "__main__":
    unittest.main()
