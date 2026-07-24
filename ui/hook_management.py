from __future__ import annotations

from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, ValidationError

from errors import PromptAdminError
from schemas.hook import HookCreate, HookRevisionCreate, HookUpdate
from schemas.prompt import StableKey
from services import (
    compiler,
    hook_impact_service,
    hook_service,
    hook_ui_service,
    prompt_service,
)
from ui.diff import side_by_side_rows, unified_diff


router = APIRouter(include_in_schema=False)
RevisionNumber = Path(ge=1)
STATUS_MESSAGES = {
    "hook-created": "Hook created.",
    "hook-updated": "Hook updated.",
    "hook-deleted": "Hook soft-deleted. It can be restored.",
    "hook-restored": "Hook restored.",
    "hook-revision-created": "Immutable Hook Revision created.",
}


def _base_context(
    request: Request,
    **values,
) -> dict:
    return {
        "request": request,
        "active_nav": "hooks",
        "status_message": STATUS_MESSAGES.get(
            request.query_params.get("status", "")
        ),
        **values,
    }


def _render(
    request: Request,
    template_name: str,
    status_code: int = 200,
    **values,
) -> Response:
    return request.app.state.templates.TemplateResponse(
        request=request,
        name=template_name,
        context=_base_context(request, **values),
        status_code=status_code,
    )


def _redirect(path: str, status: str | None = None) -> RedirectResponse:
    if status is not None:
        separator = "&" if "?" in path else "?"
        path = f"{path}{separator}{urlencode({'status': status})}"
    return RedirectResponse(path, status_code=303)


async def _read_urlencoded_form(request: Request) -> dict[str, str]:
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("application/x-www-form-urlencoded"):
        raise PromptAdminError(
            "bad_request",
            "Unsupported form content type.",
            400,
        )

    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


def _field_errors(exception: ValidationError) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    for error in exception.errors():
        location = error.get("loc", ())
        field = str(location[-1]) if location else "__root__"
        errors.setdefault(field, []).append(error["msg"])
    return errors


def _model_data(model: type[BaseModel], values: dict) -> BaseModel:
    return model(**values)


def _categories() -> list[str]:
    return sorted(
        {
            hook["category"]
            for hook in hook_ui_service.list_hook_summaries(
                include_deleted=True
            )
            if hook["category"]
        }
    )


def _hook_form(values: dict[str, str], hook_key: str = "") -> dict:
    return {
        "hook_key": hook_key or values.get("hook_key", ""),
        "display_name": values.get("display_name", ""),
        "description": values.get("description", ""),
        "category": values.get("category", ""),
    }


def _revision_form(values: dict[str, str]) -> dict:
    return {
        "hook_group": values.get("hook_group", ""),
        "hook_content": values.get("hook_content", ""),
        "priority": values.get("priority", "100"),
        "is_enabled": values.get("is_enabled", "") == "on",
        "change_note": values.get("change_note", ""),
    }


def _assert_active_hook(hook: dict) -> None:
    if hook["deleted_at"] is not None:
        raise PromptAdminError(
            "hook_deleted",
            "Deleted Hook must be restored before this operation.",
            409,
        )


@router.get("/hooks", response_class=HTMLResponse)
def hook_list(
    request: Request,
    category: str = "",
    state: str = "active",
) -> Response:
    if state not in {"active", "deleted", "all"}:
        state = "active"

    hooks = hook_ui_service.list_hook_summaries(
        category=category or None,
        include_deleted=state != "active",
    )
    if state == "deleted":
        hooks = [hook for hook in hooks if hook["deleted_at"] is not None]
    elif state == "active":
        hooks = [hook for hook in hooks if hook["deleted_at"] is None]

    return _render(
        request,
        "hooks/list.html",
        hooks=hooks,
        categories=_categories(),
        filters={"category": category, "state": state},
    )


@router.get("/hooks/new", response_class=HTMLResponse)
def hook_create_form(request: Request) -> Response:
    return _render(
        request,
        "hooks/form.html",
        heading="Create Hook",
        submit_label="Create Hook",
        action="/hooks",
        form=_hook_form({}),
        errors={},
        immutable_key=False,
    )


@router.post("/hooks", response_class=HTMLResponse)
async def hook_create(request: Request) -> Response:
    form = _hook_form(await _read_urlencoded_form(request))
    try:
        data = _model_data(HookCreate, form)
        hook = hook_service.create_hook(data)
    except ValidationError as exception:
        return _render(
            request,
            "hooks/form.html",
            status_code=422,
            heading="Create Hook",
            submit_label="Create Hook",
            action="/hooks",
            form=form,
            errors=_field_errors(exception),
            error_summary="Check the highlighted fields.",
            immutable_key=False,
        )
    except PromptAdminError as exception:
        return _render(
            request,
            "hooks/form.html",
            status_code=exception.status_code,
            heading="Create Hook",
            submit_label="Create Hook",
            action="/hooks",
            form=form,
            errors={},
            error_summary=exception.message,
            immutable_key=False,
        )

    return _redirect(
        f"/hooks/{hook['hook_key']}",
        "hook-created",
    )


@router.get("/hooks/{hook_key}/edit", response_class=HTMLResponse)
def hook_edit_form(request: Request, hook_key: StableKey) -> Response:
    detail = hook_ui_service.get_hook_detail(hook_key)
    hook = detail["hook"]
    _assert_active_hook(hook)
    return _render(
        request,
        "hooks/form.html",
        heading="Edit Hook",
        submit_label="Save Changes",
        action=f"/hooks/{hook_key}/edit",
        form=hook,
        errors={},
        immutable_key=True,
    )


@router.post("/hooks/{hook_key}/edit", response_class=HTMLResponse)
async def hook_edit(request: Request, hook_key: StableKey) -> Response:
    form = _hook_form(await _read_urlencoded_form(request), hook_key)
    values = {
        "display_name": form["display_name"],
        "description": form["description"],
        "category": form["category"],
    }
    try:
        data = _model_data(HookUpdate, values)
        hook_service.update_hook(hook_key, data)
    except ValidationError as exception:
        return _render(
            request,
            "hooks/form.html",
            status_code=422,
            heading="Edit Hook",
            submit_label="Save Changes",
            action=f"/hooks/{hook_key}/edit",
            form=form,
            errors=_field_errors(exception),
            error_summary="Check the highlighted fields.",
            immutable_key=True,
        )
    except PromptAdminError as exception:
        return _render(
            request,
            "hooks/form.html",
            status_code=exception.status_code,
            heading="Edit Hook",
            submit_label="Save Changes",
            action=f"/hooks/{hook_key}/edit",
            form=form,
            errors={},
            error_summary=exception.message,
            immutable_key=True,
        )

    return _redirect(f"/hooks/{hook_key}", "hook-updated")


@router.post("/hooks/{hook_key}/delete")
def hook_delete(hook_key: StableKey) -> RedirectResponse:
    hook_service.delete_hook(hook_key)
    return _redirect(f"/hooks/{hook_key}", "hook-deleted")


@router.post("/hooks/{hook_key}/restore")
def hook_restore(hook_key: StableKey) -> RedirectResponse:
    hook_service.restore_hook(hook_key)
    return _redirect(f"/hooks/{hook_key}", "hook-restored")


@router.get(
    "/hooks/{hook_key}/revisions/new",
    response_class=HTMLResponse,
)
def hook_revision_create_form(
    request: Request,
    hook_key: StableKey,
    from_revision: int | None = None,
) -> Response:
    detail = hook_ui_service.get_hook_detail(hook_key)
    hook = detail["hook"]
    _assert_active_hook(hook)
    form = {
        "hook_group": "",
        "hook_content": "",
        "priority": "100",
        "is_enabled": True,
        "change_note": "",
    }
    if from_revision is not None:
        copied = hook_ui_service.get_revision(hook_key, from_revision)[
            "revision"
        ]
        form = {
            "hook_group": copied["hook_group"],
            "hook_content": copied["hook_content"],
            "priority": str(copied["priority"]),
            "is_enabled": copied["is_enabled"],
            "change_note": "",
        }

    return _render(
        request,
        "hook_revisions/form.html",
        hook=hook,
        form=form,
        errors={},
        copied_from=from_revision,
    )


@router.post(
    "/hooks/{hook_key}/revisions",
    response_class=HTMLResponse,
)
async def hook_revision_create(
    request: Request,
    hook_key: StableKey,
) -> Response:
    detail = hook_ui_service.get_hook_detail(hook_key)
    hook = detail["hook"]
    form = _revision_form(await _read_urlencoded_form(request))
    try:
        data = _model_data(HookRevisionCreate, form)
        revision = hook_service.create_revision(hook_key, data)
    except ValidationError as exception:
        return _render(
            request,
            "hook_revisions/form.html",
            status_code=422,
            hook=hook,
            form=form,
            errors=_field_errors(exception),
            error_summary="Check the highlighted fields.",
            copied_from=None,
        )
    except PromptAdminError as exception:
        return _render(
            request,
            "hook_revisions/form.html",
            status_code=exception.status_code,
            hook=hook,
            form=form,
            errors={},
            error_summary=exception.message,
            copied_from=None,
        )

    return _redirect(
        f"/hooks/{hook_key}/revisions/{revision['revision_number']}",
        "hook-revision-created",
    )


@router.get(
    "/hooks/{hook_key}/revisions/{revision}",
    response_class=HTMLResponse,
)
def hook_revision_detail(
    request: Request,
    hook_key: StableKey,
    revision: int = RevisionNumber,
) -> Response:
    data = hook_ui_service.get_revision(hook_key, revision)
    return _render(
        request,
        "hook_revisions/detail.html",
        hook=data["hook"],
        revision=data["revision"],
    )


@router.get("/hooks/{hook_key}/compare", response_class=HTMLResponse)
def hook_compare(
    request: Request,
    hook_key: StableKey,
    from_revision: int | None = None,
    to_revision: int | None = None,
) -> Response:
    detail = hook_ui_service.get_hook_detail(hook_key)
    hook = detail["hook"]
    revisions = detail["revisions"]
    if len(revisions) < 2:
        return _render(
            request,
            "hook_revisions/compare.html",
            hook=hook,
            revisions=revisions,
            old_revision=None,
            new_revision=None,
            unified_lines=[],
            side_rows=[],
        )

    by_number = {
        revision["revision_number"]: revision for revision in revisions
    }
    if from_revision is None and to_revision is None:
        old_revision, new_revision = revisions[-2:]
    else:
        old_number = from_revision or revisions[-2]["revision_number"]
        new_number = to_revision or revisions[-1]["revision_number"]
        if old_number not in by_number or new_number not in by_number:
            raise PromptAdminError(
                "hook_revision_not_found",
                "Hook Revision was not found.",
                404,
            )
        old_revision = by_number[old_number]
        new_revision = by_number[new_number]

    old_label = f"{hook_key}:r{old_revision['revision_number']}"
    new_label = f"{hook_key}:r{new_revision['revision_number']}"
    return _render(
        request,
        "hook_revisions/compare.html",
        hook=hook,
        revisions=revisions,
        old_revision=old_revision,
        new_revision=new_revision,
        unified_lines=unified_diff(
            old_revision["hook_content"],
            new_revision["hook_content"],
            old_label,
            new_label,
        ),
        side_rows=side_by_side_rows(
            old_revision["hook_content"],
            new_revision["hook_content"],
        ),
    )


@router.get("/hooks/{hook_key}/impact", response_class=HTMLResponse)
def hook_impact(request: Request, hook_key: StableKey) -> Response:
    impact = hook_impact_service.get_hook_impact(hook_key)
    return _render(
        request,
        "hooks/impact.html",
        **impact,
    )


@router.get("/hooks/{hook_key}", response_class=HTMLResponse)
def hook_detail(request: Request, hook_key: StableKey) -> Response:
    detail = hook_ui_service.get_hook_detail(hook_key)
    return _render(
        request,
        "hooks/detail.html",
        hook=detail["hook"],
        revisions=detail["revisions"],
    )


@router.get(
    "/prompts/{prompt_key}/variants/{variant_key}/revisions/"
    "{revision}/compiled-preview",
    response_class=HTMLResponse,
)
def prompt_compiled_preview(
    request: Request,
    prompt_key: StableKey,
    variant_key: StableKey,
    revision: int = RevisionNumber,
) -> Response:
    prompt = prompt_service.get_prompt(prompt_key)
    variant = prompt_service.get_variant(prompt_key, variant_key)
    prompt_revision = prompt_service.get_revision(
        prompt_key,
        variant_key,
        revision,
    )
    preview = compiler.preview_prompt_revision(
        prompt_key,
        variant_key,
        revision,
    )
    return _render(
        request,
        "revisions/compiled_preview.html",
        prompt=prompt,
        variant=variant,
        revision=prompt_revision,
        preview=preview,
    )
