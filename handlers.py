import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, quote, urlparse

from compiler import compile_prompt_text
from db import db_health_check
from exporting import build_download_payload, build_export_payload, parse_import_payload
from hook_repository import (
    get_hook,
    import_hooks,
    list_hook_versions,
    list_hooks,
    permanently_delete_hook,
    restore_hook,
    save_hook,
    soft_delete_hook,
)
from render import (
    render_api_docs,
    render_delete_confirmation,
    render_deleted,
    render_families,
    render_family_delete_confirmation,
    render_family_form,
    render_family_overview,
    render_form,
    render_history,
    render_hook_delete_confirmation,
    render_hook_form,
    render_hook_history,
    render_hooks,
    render_import_page,
    render_import_result,
    render_index,
    render_message_page,
    render_prompt_preview,
)
from repository import (
    build_prompt_clone,
    get_prompt,
    get_prompt_family,
    import_prompts,
    list_active_prompts,
    list_filtered_prompt_summaries,
    list_prompt_categories,
    list_prompt_families,
    list_prompt_family_versions,
    list_prompt_summaries,
    list_prompt_versions,
    normalize_bool,
    permanently_delete_prompt,
    permanently_delete_prompt_family,
    restore_prompt,
    restore_prompt_family,
    save_prompt,
    save_prompt_family,
    soft_delete_prompt,
    soft_delete_prompt_family,
)
from static_files import resolve_static_file
from validation import normalize_hook_group, validate_hook_text, validate_key, validate_prompt_text


def clone_key(value):
    return f"{value}_copy"


def first_query_value(query, key, default=""):
    return query.get(key, [default])[0].strip()


def prompt_keys_from_query(query):
    raw_values = []
    raw_values.extend(query.get("key", []))
    raw_values.extend(query.get("keys", []))

    prompt_keys = []
    seen = set()
    for raw_value in raw_values:
        for item in raw_value.split(","):
            prompt_key = item.strip()
            if not prompt_key:
                continue
            validated = validate_key(prompt_key)
            if validated in seen:
                continue
            seen.add(validated)
            prompt_keys.append(validated)
    return prompt_keys


def missing_prompt_keys(requested_keys, prompts):
    if not requested_keys:
        return []
    returned_keys = {prompt["prompt_key"] for prompt in prompts}
    return [prompt_key for prompt_key in requested_keys if prompt_key not in returned_keys]


def filter_prompt_families(families, query):
    query = (query or "").strip().lower()
    if not query:
        return families
    return [
        family for family in families
        if query in family.get("family_key", "").lower()
        or query in family.get("description", "").lower()
    ]


def timestamp_to_json(value):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError("Timestamp value must support isoformat().")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/healthz":
                return self.handle_health()
            if parsed.path == "/api/prompts/compiled":
                return self.handle_compiled_prompts_api(query)
            if parsed.path.startswith("/static/"):
                return self.handle_static(parsed.path.removeprefix("/static/"))
            if parsed.path == "/":
                return self.handle_prompt_list(query)
            if parsed.path == "/api-docs":
                return self.send_html(render_api_docs())
            if parsed.path == "/new":
                return self.send_html(render_form(families=list_prompt_families()))
            if parsed.path == "/edit":
                return self.handle_prompt_edit(query)
            if parsed.path == "/clone":
                return self.handle_prompt_clone(query)
            if parsed.path == "/preview":
                return self.handle_prompt_preview(query)
            if parsed.path == "/confirm-delete":
                return self.send_html(render_delete_confirmation(validate_key(query.get("key", [""])[0])))
            if parsed.path == "/history":
                prompt_key = validate_key(query.get("key", [""])[0])
                return self.send_html(render_history(prompt_key, list_prompt_versions(prompt_key)))
            if parsed.path == "/families":
                return self.handle_family_list(query)
            if parsed.path == "/family":
                return self.handle_family_overview(query)
            if parsed.path == "/family-new":
                return self.send_html(render_family_form())
            if parsed.path == "/family-edit":
                return self.handle_family_edit(query)
            if parsed.path == "/family-confirm-delete":
                return self.handle_family_confirm_delete(query)
            if parsed.path == "/hooks":
                return self.send_html(render_hooks(list_hooks()))
            if parsed.path == "/hook-new":
                return self.send_html(render_hook_form())
            if parsed.path == "/hook-edit":
                return self.handle_hook_edit(query)
            if parsed.path == "/hook-clone":
                return self.handle_hook_clone(query)
            if parsed.path == "/hook-confirm-delete":
                return self.send_html(render_hook_delete_confirmation(validate_key(query.get("key", [""])[0])))
            if parsed.path == "/hook-history":
                hook_key = validate_key(query.get("key", [""])[0])
                return self.send_html(render_hook_history(hook_key, list_hook_versions(hook_key)))
            if parsed.path == "/deleted":
                return self.send_html(
                    render_deleted(
                        list_prompt_summaries(include_deleted=True),
                        list_hooks(include_deleted=True),
                        list_prompt_families(include_deleted=True),
                    )
                )
            if parsed.path == "/download":
                return self.handle_download(query)
            if parsed.path == "/export":
                return self.send_file(*build_export_payload(include_deleted=False))
            if parsed.path == "/import":
                return self.send_html(render_import_page())
            return self.send_html(render_message_page("Not found", "Page not found."), HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            if parsed.path.startswith("/api/"):
                return self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return self.send_html(render_message_page("Bad request", str(exc)), HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.log_error("Unhandled error: %s", exc)
            if parsed.path.startswith("/api/"):
                return self.send_json({"error": "Request failed."}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return self.send_html(render_message_page("Error", "Request failed."), HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        parsed = urlparse(self.path)
        if not self.is_local_post_request():
            return self.send_html(render_message_page("Forbidden", "Cross-site requests are not allowed."), HTTPStatus.FORBIDDEN)

        form = self.read_form()
        try:
            if parsed.path == "/save":
                return self.handle_save(form)
            if parsed.path == "/validate":
                return self.handle_validate(form)
            if parsed.path == "/delete":
                soft_delete_prompt(validate_key(form.get("prompt_key", [""])[0]))
                return self.redirect("/")
            if parsed.path == "/purge":
                permanently_delete_prompt(validate_key(form.get("prompt_key", [""])[0]))
                return self.redirect("/deleted")
            if parsed.path == "/restore":
                restore_prompt(validate_key(form.get("prompt_key", [""])[0]))
                return self.redirect("/deleted")
            if parsed.path == "/family-save":
                return self.handle_family_save(form)
            if parsed.path == "/family-delete":
                soft_delete_prompt_family(validate_key(form.get("family_key", [""])[0]))
                return self.redirect("/families")
            if parsed.path == "/family-purge":
                permanently_delete_prompt_family(validate_key(form.get("family_key", [""])[0]))
                return self.redirect("/deleted")
            if parsed.path == "/family-restore":
                restore_prompt_family(validate_key(form.get("family_key", [""])[0]))
                return self.redirect("/deleted")
            if parsed.path == "/hook-save":
                return self.handle_hook_save(form)
            if parsed.path == "/hook-validate":
                return self.handle_hook_validate(form)
            if parsed.path == "/hook-delete":
                soft_delete_hook(validate_key(form.get("hook_key", [""])[0]))
                return self.redirect("/hooks")
            if parsed.path == "/hook-purge":
                permanently_delete_hook(validate_key(form.get("hook_key", [""])[0]))
                return self.redirect("/deleted")
            if parsed.path == "/hook-restore":
                restore_hook(validate_key(form.get("hook_key", [""])[0]))
                return self.redirect("/deleted")
            if parsed.path == "/import":
                return self.handle_import(form)
            return self.send_html(render_message_page("Not found", "Page not found."), HTTPStatus.NOT_FOUND)
        except Exception as exc:
            if parsed.path == "/import":
                return self.send_html(render_import_page(error=str(exc)), HTTPStatus.BAD_REQUEST)
            if parsed.path == "/family-save":
                return self.send_html(render_family_form(self.safe_family_from_form(form), error=str(exc)), HTTPStatus.BAD_REQUEST)
            if parsed.path.startswith("/family-"):
                return self.send_html(render_message_page("Bad request", str(exc)), HTTPStatus.BAD_REQUEST)
            if parsed.path.startswith("/hook-"):
                return self.send_html(render_hook_form(self.safe_hook_from_form(form), error=str(exc)), HTTPStatus.BAD_REQUEST)
            prompt = self.safe_prompt_from_form(form)
            return self.send_html(
                render_form(
                    prompt,
                    error=str(exc),
                    family_versions=self.prompt_family_versions(prompt),
                    families=list_prompt_families(),
                ),
                HTTPStatus.BAD_REQUEST,
            )

    def handle_prompt_list(self, query):
        status = (first_query_value(query, "status", "all") or "all").strip().lower()
        if status not in {"all", "active", "inactive"}:
            status = "all"
        filters = {
            "category": first_query_value(query, "category"),
            "status": status,
            "q": first_query_value(query, "q"),
        }
        summaries = list_filtered_prompt_summaries(filters["category"], filters["status"], filters["q"])
        return self.send_html(render_index(summaries, list_prompt_categories(), filters))

    def handle_family_list(self, query):
        filters = {"q": first_query_value(query, "q")}
        families = filter_prompt_families(list_prompt_families(), filters["q"])
        return self.send_html(render_families(families, filters))

    def handle_compiled_prompts_api(self, query):
        category = first_query_value(query, "category")
        prompt_keys = prompt_keys_from_query(query)

        if not category and not prompt_keys:
            return self.send_json({"error": "Provide category, key, or keys query parameter."}, HTTPStatus.BAD_REQUEST)

        prompts = list_active_prompts(category=category, prompt_keys=prompt_keys)
        compiled_prompts = [self.compiled_prompt_payload(prompt) for prompt in prompts]
        return self.send_json(
            {
                "category": category or None,
                "keys": prompt_keys,
                "missing_keys": missing_prompt_keys(prompt_keys, prompts),
                "count": len(compiled_prompts),
                "prompts": compiled_prompts,
            }
        )

    def compiled_prompt_payload(self, prompt):
        compiled = compile_prompt_text(prompt["system_prompt"])
        return {
            "prompt_key": prompt["prompt_key"],
            "category": prompt["category"],
            "is_active": prompt["is_active"],
            "updated_at": timestamp_to_json(prompt["updated_at"]),
            "raw_prompt": compiled["raw_prompt"],
            "compiled_prompt": compiled["compiled_prompt"],
            "detected_groups": compiled["detected_groups"],
            "resolved_hooks": [
                {
                    "hook_key": hook["hook_key"],
                    "hook_group": hook["hook_group"],
                    "description": hook.get("description", ""),
                    "category": hook.get("category", ""),
                    "priority": hook.get("priority"),
                    "is_active": hook.get("is_active"),
                }
                for hook in compiled["resolved_hooks"]
            ],
            "unresolved_groups": compiled["unresolved_groups"],
        }

    def handle_prompt_edit(self, query):
        prompt_key = validate_key(query.get("key", [""])[0])
        prompt = get_prompt(prompt_key)
        if not prompt:
            return self.send_html(render_message_page("Not found", "Prompt not found."), HTTPStatus.NOT_FOUND)
        return self.send_html(render_form(prompt, family_versions=self.prompt_family_versions(prompt), families=list_prompt_families()))

    def handle_prompt_clone(self, query):
        prompt_key = validate_key(query.get("key", [""])[0])
        cloned_prompt = build_prompt_clone(prompt_key)
        if not cloned_prompt:
            return self.send_html(render_message_page("Not found", "Prompt not found."), HTTPStatus.NOT_FOUND)
        return self.send_html(render_form(cloned_prompt, family_versions=self.prompt_family_versions(cloned_prompt), families=list_prompt_families()))

    def handle_prompt_preview(self, query):
        prompt_key = validate_key(query.get("key", [""])[0])
        prompt = get_prompt(prompt_key)
        if not prompt:
            return self.send_html(render_message_page("Not found", "Prompt not found."), HTTPStatus.NOT_FOUND)
        return self.send_html(render_prompt_preview(prompt_key, compile_prompt_text(prompt["system_prompt"])))

    def handle_family_overview(self, query):
        family_key = validate_key(query.get("key", [""])[0])
        family = get_prompt_family(family_key)
        if not family:
            return self.send_html(render_message_page("Not found", "Prompt family not found."), HTTPStatus.NOT_FOUND)
        return self.send_html(render_family_overview(family, list_prompt_family_versions(family_key)))

    def handle_family_edit(self, query):
        family_key = validate_key(query.get("key", [""])[0])
        family = get_prompt_family(family_key)
        if not family:
            return self.send_html(render_message_page("Not found", "Prompt family not found."), HTTPStatus.NOT_FOUND)
        return self.send_html(render_family_form(family))

    def handle_family_confirm_delete(self, query):
        family_key = validate_key(query.get("key", [""])[0])
        family = get_prompt_family(family_key)
        if not family:
            return self.send_html(render_message_page("Not found", "Prompt family not found."), HTTPStatus.NOT_FOUND)
        return self.send_html(render_family_delete_confirmation(family))

    def handle_hook_edit(self, query):
        hook_key = validate_key(query.get("key", [""])[0])
        hook = get_hook(hook_key)
        if not hook:
            return self.send_html(render_message_page("Not found", "Hook not found."), HTTPStatus.NOT_FOUND)
        return self.send_html(render_hook_form(hook))

    def handle_hook_clone(self, query):
        hook_key = validate_key(query.get("key", [""])[0])
        hook = get_hook(hook_key)
        if not hook:
            return self.send_html(render_message_page("Not found", "Hook not found."), HTTPStatus.NOT_FOUND)
        cloned_hook = dict(hook)
        cloned_hook["hook_key"] = clone_key(hook_key)
        cloned_hook["_is_clone"] = True
        return self.send_html(render_hook_form(cloned_hook))

    def is_local_post_request(self):
        origin = self.headers.get("Origin") or ""
        referer = self.headers.get("Referer") or ""
        allowed = ("http://localhost", "http://127.0.0.1", "http://[::1]")
        return not (origin or referer) or origin.startswith(allowed) or referer.startswith(allowed)

    def handle_health(self):
        try:
            db_ok = db_health_check()
        except Exception:
            db_ok = False
        return self.send_json({"status": "ok" if db_ok else "degraded", "database": db_ok}, status=HTTPStatus.OK if db_ok else HTTPStatus.SERVICE_UNAVAILABLE)

    def handle_static(self, relative_path):
        try:
            body, content_type = resolve_static_file(relative_path)
            return self.send_bytes(body, content_type)
        except ValueError:
            return self.send_html(render_message_page("Forbidden", "Static file path is not allowed."), HTTPStatus.FORBIDDEN)
        except FileNotFoundError:
            return self.send_html(render_message_page("Not found", "Static file not found."), HTTPStatus.NOT_FOUND)

    def handle_download(self, query):
        prompt_key = validate_key(query.get("key", [""])[0])
        prompt = get_prompt(prompt_key)
        if not prompt:
            return self.send_html(render_message_page("Not found", "Prompt not found."), HTTPStatus.NOT_FOUND)
        content, content_type, filename = build_download_payload(prompt["prompt_key"], prompt["system_prompt"], query.get("format", [""])[0].strip().lower())
        return self.send_file(content, content_type, filename)

    def handle_save(self, form):
        prompt = self.prompt_from_form(form)
        save_prompt(
            prompt["prompt_key"],
            prompt["system_prompt"],
            prompt["category"],
            prompt["is_active"],
            prompt["prompt_family_key"],
            prompt["family_version"],
            prompt["clone_source_key"],
            prompt["selected_prompt_family_key"],
        )
        return self.redirect(f"/edit?key={quote(prompt['prompt_key'], safe='')}")

    def handle_validate(self, form):
        prompt = self.prompt_from_form(form)
        return self.send_html(render_form(prompt, validation_warnings=validate_prompt_text(prompt["system_prompt"]), family_versions=self.prompt_family_versions(prompt), families=list_prompt_families()))

    def handle_family_save(self, form):
        family = self.family_from_form(form)
        save_prompt_family(family["family_key"], family["description"])
        return self.redirect(f"/family-edit?key={quote(family['family_key'], safe='')}")

    def handle_hook_save(self, form):
        hook = self.hook_from_form(form)
        save_hook(hook["hook_key"], hook["hook_group"], hook["hook_content"], hook["description"], hook["category"], hook["priority"], hook["is_active"])
        return self.redirect(f"/hook-edit?key={quote(hook['hook_key'], safe='')}")

    def handle_hook_validate(self, form):
        hook = self.hook_from_form(form)
        return self.send_html(render_hook_form(hook, validation_warnings=validate_hook_text(hook["hook_content"])))

    def handle_import(self, form):
        raw_json = form.get("payload", [""])[0]
        dry_run = form.get("mode", ["preview"])[0] != "apply"
        payload = parse_import_payload(raw_json)
        plan = {
            "families": self.import_prompt_families(payload["families"], dry_run=dry_run),
            "prompts": import_prompts(payload["prompts"], dry_run=dry_run),
            "hooks": import_hooks(payload["hooks"], dry_run=dry_run),
        }
        return self.send_html(render_import_page(result_html=render_import_result(plan, dry_run)))

    def import_prompt_families(self, families, dry_run=True):
        plan = {"create": [], "update": []}
        for family in families:
            family_key = validate_key(family.get("family_key"))
            existing = get_prompt_family(family_key, include_deleted=True)
            target = plan["update"] if existing else plan["create"]
            target.append(family_key)
            if not dry_run:
                save_prompt_family(family_key, family.get("description", ""))
        return plan

    def prompt_from_form(self, form):
        clone_source_key = form.get("clone_source_key", [""])[0]
        return {
            "prompt_key": validate_key(form.get("prompt_key", [""])[0]),
            "system_prompt": form.get("system_prompt", [""])[0],
            "category": form.get("category", [""])[0],
            "prompt_family_key": form.get("prompt_family_key", [""])[0],
            "family_version": form.get("family_version", [""])[0],
            "selected_prompt_family_key": form.get("selected_prompt_family_key", [""])[0],
            "clone_source_key": clone_source_key,
            "_is_clone": bool(clone_source_key),
            "is_active": normalize_bool(form.get("is_active", [""])[0]),
        }

    def family_from_form(self, form):
        return {
            "family_key": validate_key(form.get("family_key", [""])[0]),
            "description": form.get("description", [""])[0],
        }

    def hook_from_form(self, form):
        return {
            "hook_key": validate_key(form.get("hook_key", [""])[0]),
            "hook_group": normalize_hook_group(form.get("hook_group", [""])[0]),
            "hook_content": form.get("hook_content", [""])[0],
            "description": form.get("description", [""])[0],
            "category": form.get("category", [""])[0],
            "priority": form.get("priority", ["100"])[0],
            "is_active": normalize_bool(form.get("is_active", [""])[0]),
        }

    def safe_prompt_from_form(self, form):
        clone_source_key = form.get("clone_source_key", [""])[0]
        return {
            "prompt_key": form.get("prompt_key", [""])[0],
            "system_prompt": form.get("system_prompt", [""])[0],
            "category": form.get("category", [""])[0],
            "prompt_family_key": form.get("prompt_family_key", [""])[0],
            "family_version": form.get("family_version", [""])[0],
            "selected_prompt_family_key": form.get("selected_prompt_family_key", [""])[0],
            "clone_source_key": clone_source_key,
            "_is_clone": bool(clone_source_key),
            "is_active": normalize_bool(form.get("is_active", [""])[0]),
        }

    def safe_family_from_form(self, form):
        return {
            "family_key": form.get("family_key", [""])[0],
            "description": form.get("description", [""])[0],
        }

    def safe_hook_from_form(self, form):
        return {
            "hook_key": form.get("hook_key", [""])[0],
            "hook_group": form.get("hook_group", [""])[0],
            "hook_content": form.get("hook_content", [""])[0],
            "description": form.get("description", [""])[0],
            "category": form.get("category", [""])[0],
            "priority": form.get("priority", ["100"])[0],
            "is_active": normalize_bool(form.get("is_active", [""])[0]),
        }

    def prompt_family_versions(self, prompt):
        family_key = (prompt or {}).get("prompt_family_key")
        if not family_key:
            return []
        try:
            family_key = validate_key(family_key)
        except Exception:
            return []
        return list_prompt_family_versions(family_key)

    def read_form(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8")
        return parse_qs(raw_body, keep_blank_values=True)

    def send_html(self, content, status=HTTPStatus.OK):
        self.send_bytes(content.encode("utf-8"), "text/html; charset=utf-8", status)

    def send_json(self, payload, status=HTTPStatus.OK):
        self.send_bytes(json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8", status)

    def send_bytes(self, body, content_type, status=HTTPStatus.OK):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location):
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def send_file(self, content, content_type, filename, status=HTTPStatus.OK):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
