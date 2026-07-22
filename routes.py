from http import HTTPStatus
from urllib.parse import parse_qs, quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from compiler import compile_prompt_text
from db import db_health_check
from exporting import (
    build_download_payload,
    build_export_payload,
    parse_import_payload,
)
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
from validation import (
    normalize_hook_group,
    validate_hook_text,
    validate_key,
    validate_prompt_text,
)


router = APIRouter()
FormData = dict[str, list[str]]


def html(content: str, status_code: int = HTTPStatus.OK) -> HTMLResponse:
    return HTMLResponse(content, status_code=status_code)


def redirect(location: str) -> RedirectResponse:
    return RedirectResponse(location, status_code=HTTPStatus.SEE_OTHER)


def download_response(
    content: str,
    content_type: str,
    filename: str,
) -> Response:
    return Response(
        content.encode("utf-8"),
        headers={
            "Content-Type": content_type,
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


async def read_form(request: Request) -> FormData:
    raw_body = (await request.body()).decode("utf-8")
    return parse_qs(raw_body, keep_blank_values=True)


def form_value(form: FormData, key: str, default: str = "") -> str:
    return form.get(key, [default])[0]


def query_value(request: Request, key: str, default: str = "") -> str:
    return request.query_params.get(key, default).strip()


def clone_key(value: str) -> str:
    return f"{value}_copy"


def prompt_keys_from_request(request: Request) -> list[str]:
    raw_values = request.query_params.getlist("key")
    raw_values.extend(request.query_params.getlist("keys"))

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


def missing_prompt_keys(
    requested_keys: list[str],
    prompts: list[dict],
) -> list[str]:
    if not requested_keys:
        return []
    returned_keys = {prompt["prompt_key"] for prompt in prompts}
    return [
        prompt_key
        for prompt_key in requested_keys
        if prompt_key not in returned_keys
    ]


def filter_prompt_families(families: list[dict], query: str) -> list[dict]:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return families
    return [
        family
        for family in families
        if normalized_query in family.get("family_key", "").lower()
        or normalized_query in family.get("description", "").lower()
    ]


def timestamp_to_json(value):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError("Timestamp value must support isoformat().")


def compiled_prompt_payload(prompt: dict) -> dict:
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


def prompt_from_form(form: FormData) -> dict:
    clone_source_key = form_value(form, "clone_source_key")
    return {
        "prompt_key": validate_key(form_value(form, "prompt_key")),
        "system_prompt": form_value(form, "system_prompt"),
        "category": form_value(form, "category"),
        "prompt_family_key": form_value(form, "prompt_family_key"),
        "family_version": form_value(form, "family_version"),
        "selected_prompt_family_key": form_value(
            form,
            "selected_prompt_family_key",
        ),
        "clone_source_key": clone_source_key,
        "_is_clone": bool(clone_source_key),
        "is_active": normalize_bool(form_value(form, "is_active")),
    }


def safe_prompt_from_form(form: FormData) -> dict:
    clone_source_key = form_value(form, "clone_source_key")
    return {
        "prompt_key": form_value(form, "prompt_key"),
        "system_prompt": form_value(form, "system_prompt"),
        "category": form_value(form, "category"),
        "prompt_family_key": form_value(form, "prompt_family_key"),
        "family_version": form_value(form, "family_version"),
        "selected_prompt_family_key": form_value(
            form,
            "selected_prompt_family_key",
        ),
        "clone_source_key": clone_source_key,
        "_is_clone": bool(clone_source_key),
        "is_active": normalize_bool(form_value(form, "is_active")),
    }


def family_from_form(form: FormData) -> dict:
    return {
        "family_key": validate_key(form_value(form, "family_key")),
        "description": form_value(form, "description"),
    }


def safe_family_from_form(form: FormData) -> dict:
    return {
        "family_key": form_value(form, "family_key"),
        "description": form_value(form, "description"),
    }


def hook_from_form(form: FormData) -> dict:
    return {
        "hook_key": validate_key(form_value(form, "hook_key")),
        "hook_group": normalize_hook_group(form_value(form, "hook_group")),
        "hook_content": form_value(form, "hook_content"),
        "description": form_value(form, "description"),
        "category": form_value(form, "category"),
        "priority": form_value(form, "priority", "100"),
        "is_active": normalize_bool(form_value(form, "is_active")),
    }


def safe_hook_from_form(form: FormData) -> dict:
    return {
        "hook_key": form_value(form, "hook_key"),
        "hook_group": form_value(form, "hook_group"),
        "hook_content": form_value(form, "hook_content"),
        "description": form_value(form, "description"),
        "category": form_value(form, "category"),
        "priority": form_value(form, "priority", "100"),
        "is_active": normalize_bool(form_value(form, "is_active")),
    }


def prompt_family_versions(prompt: dict | None) -> list[dict]:
    family_key = (prompt or {}).get("prompt_family_key")
    if not family_key:
        return []
    try:
        family_key = validate_key(family_key)
    except Exception:
        return []
    return list_prompt_family_versions(family_key)


def import_prompt_families(
    families: list[dict],
    dry_run: bool = True,
) -> dict[str, list[str]]:
    plan = {"create": [], "update": []}
    for family in families:
        family_key = validate_key(family.get("family_key"))
        existing = get_prompt_family(family_key, include_deleted=True)
        target = plan["update"] if existing else plan["create"]
        target.append(family_key)
        if not dry_run:
            save_prompt_family(family_key, family.get("description", ""))
    return plan


def ensure_local_post_request(request: Request) -> None:
    origin = request.headers.get("Origin") or ""
    referer = request.headers.get("Referer") or ""
    allowed = (
        "http://localhost",
        "https://localhost",
        "http://127.0.0.1",
        "https://127.0.0.1",
        "http://[::1]",
        "https://[::1]",
    )
    if (origin or referer) and not (
        origin.startswith(allowed) or referer.startswith(allowed)
    ):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Cross-site requests are not allowed.",
        )


@router.get("/healthz")
def health() -> JSONResponse:
    try:
        database_ok = db_health_check()
    except Exception:
        database_ok = False
    return JSONResponse(
        {
            "status": "ok" if database_ok else "degraded",
            "database": database_ok,
        },
        status_code=(
            HTTPStatus.OK
            if database_ok
            else HTTPStatus.SERVICE_UNAVAILABLE
        ),
    )


@router.get("/api/prompts/compiled")
def compiled_prompts(request: Request) -> JSONResponse:
    category = query_value(request, "category")
    prompt_keys = prompt_keys_from_request(request)
    if not category and not prompt_keys:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Provide category, key, or keys query parameter.",
        )

    prompts = list_active_prompts(
        category=category,
        prompt_keys=prompt_keys,
    )
    compiled_prompts_payload = [
        compiled_prompt_payload(prompt)
        for prompt in prompts
    ]
    return JSONResponse(
        {
            "category": category or None,
            "keys": prompt_keys,
            "missing_keys": missing_prompt_keys(prompt_keys, prompts),
            "count": len(compiled_prompts_payload),
            "prompts": compiled_prompts_payload,
        }
    )


@router.get("/")
def prompt_list(request: Request) -> HTMLResponse:
    status = (query_value(request, "status", "all") or "all").lower()
    if status not in {"all", "active", "inactive"}:
        status = "all"
    filters = {
        "category": query_value(request, "category"),
        "status": status,
        "q": query_value(request, "q"),
    }
    summaries = list_filtered_prompt_summaries(
        filters["category"],
        filters["status"],
        filters["q"],
    )
    return html(render_index(summaries, list_prompt_categories(), filters))


@router.get("/api-docs")
def api_docs() -> HTMLResponse:
    return html(render_api_docs())


@router.get("/new")
def prompt_new() -> HTMLResponse:
    return html(render_form(families=list_prompt_families()))


@router.get("/edit")
def prompt_edit(key: str = "") -> HTMLResponse:
    prompt_key = validate_key(key)
    prompt = get_prompt(prompt_key)
    if not prompt:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Prompt not found.")
    return html(
        render_form(
            prompt,
            family_versions=prompt_family_versions(prompt),
            families=list_prompt_families(),
        )
    )


@router.get("/clone")
def prompt_clone(key: str = "") -> HTMLResponse:
    prompt_key = validate_key(key)
    prompt = build_prompt_clone(prompt_key)
    if not prompt:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Prompt not found.")
    return html(
        render_form(
            prompt,
            family_versions=prompt_family_versions(prompt),
            families=list_prompt_families(),
        )
    )


@router.get("/preview")
def prompt_preview(key: str = "") -> HTMLResponse:
    prompt_key = validate_key(key)
    prompt = get_prompt(prompt_key)
    if not prompt:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Prompt not found.")
    return html(
        render_prompt_preview(
            prompt_key,
            compile_prompt_text(prompt["system_prompt"]),
        )
    )


@router.get("/confirm-delete")
def prompt_confirm_delete(key: str = "") -> HTMLResponse:
    return html(render_delete_confirmation(validate_key(key)))


@router.get("/history")
def prompt_history(key: str = "") -> HTMLResponse:
    prompt_key = validate_key(key)
    return html(render_history(prompt_key, list_prompt_versions(prompt_key)))


@router.get("/families")
def family_list(request: Request) -> HTMLResponse:
    filters = {"q": query_value(request, "q")}
    families = filter_prompt_families(
        list_prompt_families(),
        filters["q"],
    )
    return html(render_families(families, filters))


@router.get("/family")
def family_overview(key: str = "") -> HTMLResponse:
    family_key = validate_key(key)
    family = get_prompt_family(family_key)
    if not family:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Prompt family not found.")
    return html(
        render_family_overview(
            family,
            list_prompt_family_versions(family_key),
        )
    )


@router.get("/family-new")
def family_new() -> HTMLResponse:
    return html(render_family_form())


@router.get("/family-edit")
def family_edit(key: str = "") -> HTMLResponse:
    family_key = validate_key(key)
    family = get_prompt_family(family_key)
    if not family:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Prompt family not found.")
    return html(render_family_form(family))


@router.get("/family-confirm-delete")
def family_confirm_delete(key: str = "") -> HTMLResponse:
    family_key = validate_key(key)
    family = get_prompt_family(family_key)
    if not family:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Prompt family not found.")
    return html(render_family_delete_confirmation(family))


@router.get("/hooks")
def hook_list() -> HTMLResponse:
    return html(render_hooks(list_hooks()))


@router.get("/hook-new")
def hook_new() -> HTMLResponse:
    return html(render_hook_form())


@router.get("/hook-edit")
def hook_edit(key: str = "") -> HTMLResponse:
    hook_key = validate_key(key)
    hook = get_hook(hook_key)
    if not hook:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Hook not found.")
    return html(render_hook_form(hook))


@router.get("/hook-clone")
def hook_clone(key: str = "") -> HTMLResponse:
    hook_key = validate_key(key)
    hook = get_hook(hook_key)
    if not hook:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Hook not found.")
    cloned_hook = dict(hook)
    cloned_hook["hook_key"] = clone_key(hook_key)
    cloned_hook["_is_clone"] = True
    return html(render_hook_form(cloned_hook))


@router.get("/hook-confirm-delete")
def hook_confirm_delete(key: str = "") -> HTMLResponse:
    return html(render_hook_delete_confirmation(validate_key(key)))


@router.get("/hook-history")
def hook_history(key: str = "") -> HTMLResponse:
    hook_key = validate_key(key)
    return html(render_hook_history(hook_key, list_hook_versions(hook_key)))


@router.get("/deleted")
def deleted_records() -> HTMLResponse:
    return html(
        render_deleted(
            list_prompt_summaries(include_deleted=True),
            list_hooks(include_deleted=True),
            list_prompt_families(include_deleted=True),
        )
    )


@router.get("/download")
def prompt_download(key: str = "", format: str = "") -> Response:
    prompt_key = validate_key(key)
    prompt = get_prompt(prompt_key)
    if not prompt:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Prompt not found.")
    return download_response(
        *build_download_payload(
            prompt["prompt_key"],
            prompt["system_prompt"],
            format.strip().lower(),
        )
    )


@router.get("/export")
def export_records() -> Response:
    return download_response(*build_export_payload(include_deleted=False))


@router.get("/import")
def import_page() -> HTMLResponse:
    return html(render_import_page())


@router.post("/save")
async def prompt_save(request: Request) -> Response:
    ensure_local_post_request(request)
    form = await read_form(request)
    try:
        prompt = prompt_from_form(form)
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
        return redirect(
            f"/edit?key={quote(prompt['prompt_key'], safe='')}"
        )
    except Exception as exception:
        prompt = safe_prompt_from_form(form)
        return html(
            render_form(
                prompt,
                error=str(exception),
                family_versions=prompt_family_versions(prompt),
                families=list_prompt_families(),
            ),
            HTTPStatus.BAD_REQUEST,
        )


@router.post("/validate")
async def prompt_validate(request: Request) -> HTMLResponse:
    ensure_local_post_request(request)
    form = await read_form(request)
    try:
        prompt = prompt_from_form(form)
        return html(
            render_form(
                prompt,
                validation_warnings=validate_prompt_text(
                    prompt["system_prompt"]
                ),
                family_versions=prompt_family_versions(prompt),
                families=list_prompt_families(),
            )
        )
    except Exception as exception:
        prompt = safe_prompt_from_form(form)
        return html(
            render_form(
                prompt,
                error=str(exception),
                family_versions=prompt_family_versions(prompt),
                families=list_prompt_families(),
            ),
            HTTPStatus.BAD_REQUEST,
        )


@router.post("/delete")
async def prompt_delete(request: Request) -> RedirectResponse:
    ensure_local_post_request(request)
    form = await read_form(request)
    soft_delete_prompt(validate_key(form_value(form, "prompt_key")))
    return redirect("/")


@router.post("/purge")
async def prompt_purge(request: Request) -> RedirectResponse:
    ensure_local_post_request(request)
    form = await read_form(request)
    permanently_delete_prompt(validate_key(form_value(form, "prompt_key")))
    return redirect("/deleted")


@router.post("/restore")
async def prompt_restore(request: Request) -> RedirectResponse:
    ensure_local_post_request(request)
    form = await read_form(request)
    restore_prompt(validate_key(form_value(form, "prompt_key")))
    return redirect("/deleted")


@router.post("/family-save")
async def family_save(request: Request) -> Response:
    ensure_local_post_request(request)
    form = await read_form(request)
    try:
        family = family_from_form(form)
        save_prompt_family(family["family_key"], family["description"])
        return redirect(
            f"/family-edit?key={quote(family['family_key'], safe='')}"
        )
    except Exception as exception:
        return html(
            render_family_form(
                safe_family_from_form(form),
                error=str(exception),
            ),
            HTTPStatus.BAD_REQUEST,
        )


@router.post("/family-delete")
async def family_delete(request: Request) -> RedirectResponse:
    ensure_local_post_request(request)
    form = await read_form(request)
    soft_delete_prompt_family(
        validate_key(form_value(form, "family_key"))
    )
    return redirect("/families")


@router.post("/family-purge")
async def family_purge(request: Request) -> RedirectResponse:
    ensure_local_post_request(request)
    form = await read_form(request)
    permanently_delete_prompt_family(
        validate_key(form_value(form, "family_key"))
    )
    return redirect("/deleted")


@router.post("/family-restore")
async def family_restore(request: Request) -> RedirectResponse:
    ensure_local_post_request(request)
    form = await read_form(request)
    restore_prompt_family(validate_key(form_value(form, "family_key")))
    return redirect("/deleted")


@router.post("/hook-save")
async def hook_save(request: Request) -> Response:
    ensure_local_post_request(request)
    form = await read_form(request)
    try:
        hook = hook_from_form(form)
        save_hook(
            hook["hook_key"],
            hook["hook_group"],
            hook["hook_content"],
            hook["description"],
            hook["category"],
            hook["priority"],
            hook["is_active"],
        )
        return redirect(
            f"/hook-edit?key={quote(hook['hook_key'], safe='')}"
        )
    except Exception as exception:
        return html(
            render_hook_form(
                safe_hook_from_form(form),
                error=str(exception),
            ),
            HTTPStatus.BAD_REQUEST,
        )


@router.post("/hook-validate")
async def hook_validate(request: Request) -> HTMLResponse:
    ensure_local_post_request(request)
    form = await read_form(request)
    try:
        hook = hook_from_form(form)
        return html(
            render_hook_form(
                hook,
                validation_warnings=validate_hook_text(
                    hook["hook_content"]
                ),
            )
        )
    except Exception as exception:
        return html(
            render_hook_form(
                safe_hook_from_form(form),
                error=str(exception),
            ),
            HTTPStatus.BAD_REQUEST,
        )


@router.post("/hook-delete")
async def hook_delete(request: Request) -> RedirectResponse:
    ensure_local_post_request(request)
    form = await read_form(request)
    soft_delete_hook(validate_key(form_value(form, "hook_key")))
    return redirect("/hooks")


@router.post("/hook-purge")
async def hook_purge(request: Request) -> RedirectResponse:
    ensure_local_post_request(request)
    form = await read_form(request)
    permanently_delete_hook(validate_key(form_value(form, "hook_key")))
    return redirect("/deleted")


@router.post("/hook-restore")
async def hook_restore(request: Request) -> RedirectResponse:
    ensure_local_post_request(request)
    form = await read_form(request)
    restore_hook(validate_key(form_value(form, "hook_key")))
    return redirect("/deleted")


@router.post("/import")
async def import_records(request: Request) -> HTMLResponse:
    ensure_local_post_request(request)
    form = await read_form(request)
    try:
        raw_json = form_value(form, "payload")
        dry_run = form_value(form, "mode", "preview") != "apply"
        payload = parse_import_payload(raw_json)
        plan = {
            "families": import_prompt_families(
                payload["families"],
                dry_run=dry_run,
            ),
            "prompts": import_prompts(
                payload["prompts"],
                dry_run=dry_run,
            ),
            "hooks": import_hooks(
                payload["hooks"],
                dry_run=dry_run,
            ),
        }
        return html(
            render_import_page(
                result_html=render_import_result(plan, dry_run)
            )
        )
    except Exception as exception:
        return html(
            render_import_page(error=str(exception)),
            HTTPStatus.BAD_REQUEST,
        )
