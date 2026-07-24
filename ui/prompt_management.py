from __future__ import annotations

import difflib
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, ValidationError

from errors import PromptAdminError
from schemas.prompt import (
    FamilyCreate,
    FamilyUpdate,
    PromptCreate,
    PromptRevisionCreate,
    PromptUpdate,
    StableKey,
    VariantCreate,
    VariantUpdate,
)
from services import prompt_service


router = APIRouter(include_in_schema=False)
RevisionNumber = Path(ge=1)
VARIANT_STATUSES = ("draft", "available", "archived")
STATUS_MESSAGES = {
    "family-created": "Family created.",
    "family-updated": "Family updated.",
    "family-deleted": "Family soft-deleted. It can be restored.",
    "family-restored": "Family restored.",
    "prompt-created": "Prompt created.",
    "prompt-updated": "Prompt updated.",
    "prompt-deleted": "Prompt soft-deleted. It can be restored.",
    "prompt-restored": "Prompt restored.",
    "variant-created": "Variant created.",
    "variant-updated": "Variant updated.",
    "revision-created": "Immutable Revision created.",
}


@dataclass(frozen=True)
class DiffRow:
    kind: str
    left_number: int | None
    left_text: str
    right_number: int | None
    right_text: str


def _base_context(
    request: Request,
    active_nav: str,
    **values,
) -> dict:
    return {
        "request": request,
        "active_nav": active_nav,
        "status_message": STATUS_MESSAGES.get(
            request.query_params.get("status", "")
        ),
        **values,
    }


def _render(
    request: Request,
    template_name: str,
    active_nav: str,
    status_code: int = 200,
    **values,
) -> Response:
    return request.app.state.templates.TemplateResponse(
        request=request,
        name=template_name,
        context=_base_context(request, active_nav, **values),
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


def _model_data(model: type[BaseModel], values: dict[str, str]) -> BaseModel:
    return model(**values)


def _optional_key(value: str) -> str | None:
    return value or None


def _families(include_deleted: bool = False) -> list[dict]:
    return prompt_service.list_families(include_deleted=include_deleted)


def _active_families() -> list[dict]:
    return [
        family
        for family in _families(include_deleted=True)
        if family["deleted_at"] is None
    ]


def _prompt_categories() -> list[str]:
    categories = {
        prompt["category"]
        for prompt in prompt_service.list_prompts(include_deleted=True)
        if prompt["category"]
    }
    return sorted(categories)


def _side_by_side_rows(old_text: str, new_text: str) -> list[DiffRow]:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    rows: list[DiffRow] = []

    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            for offset, (old_line, new_line) in enumerate(
                zip(
                    old_lines[old_start:old_end],
                    new_lines[new_start:new_end],
                    strict=True,
                )
            ):
                rows.append(
                    DiffRow(
                        "equal",
                        old_start + offset + 1,
                        old_line,
                        new_start + offset + 1,
                        new_line,
                    )
                )
            continue

        old_chunk = old_lines[old_start:old_end]
        new_chunk = new_lines[new_start:new_end]
        width = max(len(old_chunk), len(new_chunk))
        for offset in range(width):
            left_exists = offset < len(old_chunk)
            right_exists = offset < len(new_chunk)
            rows.append(
                DiffRow(
                    tag,
                    old_start + offset + 1 if left_exists else None,
                    old_chunk[offset] if left_exists else "",
                    new_start + offset + 1 if right_exists else None,
                    new_chunk[offset] if right_exists else "",
                )
            )

    return rows


def _unified_diff(
    prompt_key: str,
    variant_key: str,
    old_revision: dict,
    new_revision: dict,
) -> list[str]:
    old_label = (
        f"{prompt_key}@{variant_key}:r"
        f"{old_revision['revision_number']}"
    )
    new_label = (
        f"{prompt_key}@{variant_key}:r"
        f"{new_revision['revision_number']}"
    )
    return list(
        difflib.unified_diff(
            old_revision["system_prompt"].splitlines(),
            new_revision["system_prompt"].splitlines(),
            fromfile=old_label,
            tofile=new_label,
            lineterm="",
        )
    )


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> Response:
    families = _families()
    prompts = prompt_service.list_prompts()
    return _render(
        request,
        "dashboard.html",
        "dashboard",
        family_count=len(families),
        prompt_count=len(prompts),
        recent_prompts=prompts[:5],
    )


@router.get("/families", response_class=HTMLResponse)
def family_list(request: Request, state: str = "active") -> Response:
    if state not in {"active", "deleted", "all"}:
        state = "active"

    families = _families(include_deleted=state != "active")
    if state == "deleted":
        families = [
            family for family in families if family["deleted_at"] is not None
        ]
    elif state == "active":
        families = [
            family for family in families if family["deleted_at"] is None
        ]

    return _render(
        request,
        "families/list.html",
        "families",
        families=families,
        state=state,
    )


@router.get("/families/new", response_class=HTMLResponse)
def family_create_form(request: Request) -> Response:
    return _render(
        request,
        "families/form.html",
        "families",
        heading="Create Family",
        submit_label="Create Family",
        action="/families",
        form={
            "family_key": "",
            "display_name": "",
            "description": "",
        },
        errors={},
        immutable_key=False,
    )


@router.post("/families", response_class=HTMLResponse)
async def family_create(request: Request) -> Response:
    form = await _read_urlencoded_form(request)
    safe_form = {
        "family_key": form.get("family_key", ""),
        "display_name": form.get("display_name", ""),
        "description": form.get("description", ""),
    }
    try:
        data = _model_data(FamilyCreate, safe_form)
        family = prompt_service.create_family(data)
    except ValidationError as exception:
        return _render(
            request,
            "families/form.html",
            "families",
            status_code=422,
            heading="Create Family",
            submit_label="Create Family",
            action="/families",
            form=safe_form,
            errors=_field_errors(exception),
            error_summary="Check the highlighted fields.",
            immutable_key=False,
        )
    except PromptAdminError as exception:
        return _render(
            request,
            "families/form.html",
            "families",
            status_code=exception.status_code,
            heading="Create Family",
            submit_label="Create Family",
            action="/families",
            form=safe_form,
            errors={},
            error_summary=exception.message,
            immutable_key=False,
        )

    return _redirect(
        f"/families/{family['family_key']}",
        "family-created",
    )


@router.get("/families/{family_key}", response_class=HTMLResponse)
def family_detail(request: Request, family_key: StableKey) -> Response:
    family = prompt_service.get_family(
        family_key,
        include_deleted=True,
    )
    prompts = prompt_service.list_prompts(
        family_key=family_key,
        include_deleted=True,
    )
    return _render(
        request,
        "families/detail.html",
        "families",
        family=family,
        prompts=prompts,
    )


@router.get("/families/{family_key}/edit", response_class=HTMLResponse)
def family_edit_form(
    request: Request,
    family_key: StableKey,
) -> Response:
    family = prompt_service.get_family(
        family_key,
        include_deleted=True,
    )
    if family["deleted_at"] is not None:
        raise PromptAdminError(
            "family_deleted",
            "Deleted Family must be restored before editing.",
            409,
        )

    return _render(
        request,
        "families/form.html",
        "families",
        heading="Edit Family",
        submit_label="Save Changes",
        action=f"/families/{family_key}/edit",
        form=family,
        errors={},
        immutable_key=True,
    )


@router.post("/families/{family_key}/edit", response_class=HTMLResponse)
async def family_edit(
    request: Request,
    family_key: StableKey,
) -> Response:
    form = await _read_urlencoded_form(request)
    safe_form = {
        "family_key": family_key,
        "display_name": form.get("display_name", ""),
        "description": form.get("description", ""),
    }
    try:
        data = _model_data(
            FamilyUpdate,
            {
                "display_name": safe_form["display_name"],
                "description": safe_form["description"],
            },
        )
        prompt_service.update_family(family_key, data)
    except ValidationError as exception:
        return _render(
            request,
            "families/form.html",
            "families",
            status_code=422,
            heading="Edit Family",
            submit_label="Save Changes",
            action=f"/families/{family_key}/edit",
            form=safe_form,
            errors=_field_errors(exception),
            error_summary="Check the highlighted fields.",
            immutable_key=True,
        )
    except PromptAdminError as exception:
        return _render(
            request,
            "families/form.html",
            "families",
            status_code=exception.status_code,
            heading="Edit Family",
            submit_label="Save Changes",
            action=f"/families/{family_key}/edit",
            form=safe_form,
            errors={},
            error_summary=exception.message,
            immutable_key=True,
        )

    return _redirect(
        f"/families/{family_key}",
        "family-updated",
    )


@router.post("/families/{family_key}/delete")
def family_delete(family_key: StableKey) -> RedirectResponse:
    prompt_service.delete_family(family_key)
    return _redirect(
        f"/families/{family_key}",
        "family-deleted",
    )


@router.post("/families/{family_key}/restore")
def family_restore(family_key: StableKey) -> RedirectResponse:
    prompt_service.restore_family(family_key)
    return _redirect(
        f"/families/{family_key}",
        "family-restored",
    )


@router.get("/prompts", response_class=HTMLResponse)
def prompt_list(
    request: Request,
    family_key: str = "",
    category: str = "",
    state: str = "active",
) -> Response:
    if state not in {"active", "deleted", "all"}:
        state = "active"

    prompts = prompt_service.list_prompts(
        family_key=_optional_key(family_key),
        category=_optional_key(category),
        include_deleted=state != "active",
    )
    if state == "deleted":
        prompts = [
            prompt for prompt in prompts if prompt["deleted_at"] is not None
        ]
    elif state == "active":
        prompts = [
            prompt for prompt in prompts if prompt["deleted_at"] is None
        ]

    return _render(
        request,
        "prompts/list.html",
        "prompts",
        prompts=prompts,
        families=_families(include_deleted=True),
        categories=_prompt_categories(),
        filters={
            "family_key": family_key,
            "category": category,
            "state": state,
        },
    )


@router.get("/prompts/new", response_class=HTMLResponse)
def prompt_create_form(request: Request) -> Response:
    return _render(
        request,
        "prompts/form.html",
        "prompts",
        heading="Create Prompt",
        submit_label="Create Prompt",
        action="/prompts",
        form={
            "prompt_key": "",
            "display_name": "",
            "description": "",
            "category": "",
            "family_key": "",
        },
        families=_active_families(),
        errors={},
        immutable_key=False,
    )


@router.post("/prompts", response_class=HTMLResponse)
async def prompt_create(request: Request) -> Response:
    form = await _read_urlencoded_form(request)
    safe_form = {
        "prompt_key": form.get("prompt_key", ""),
        "display_name": form.get("display_name", ""),
        "description": form.get("description", ""),
        "category": form.get("category", ""),
        "family_key": form.get("family_key", ""),
    }
    values = {
        **safe_form,
        "family_key": _optional_key(safe_form["family_key"]),
    }

    try:
        data = _model_data(PromptCreate, values)
        prompt = prompt_service.create_prompt(data)
    except ValidationError as exception:
        return _render(
            request,
            "prompts/form.html",
            "prompts",
            status_code=422,
            heading="Create Prompt",
            submit_label="Create Prompt",
            action="/prompts",
            form=safe_form,
            families=_active_families(),
            errors=_field_errors(exception),
            error_summary="Check the highlighted fields.",
            immutable_key=False,
        )
    except PromptAdminError as exception:
        return _render(
            request,
            "prompts/form.html",
            "prompts",
            status_code=exception.status_code,
            heading="Create Prompt",
            submit_label="Create Prompt",
            action="/prompts",
            form=safe_form,
            families=_active_families(),
            errors={},
            error_summary=exception.message,
            immutable_key=False,
        )

    return _redirect(
        f"/prompts/{prompt['prompt_key']}",
        "prompt-created",
    )


@router.get("/prompts/{prompt_key}", response_class=HTMLResponse)
def prompt_detail(request: Request, prompt_key: StableKey) -> Response:
    prompt = prompt_service.get_prompt(
        prompt_key,
        include_deleted=True,
    )
    variants = (
        prompt_service.list_variants(prompt_key)
        if prompt["deleted_at"] is None
        else []
    )
    return _render(
        request,
        "prompts/detail.html",
        "prompts",
        prompt=prompt,
        variants=variants,
    )


@router.get("/prompts/{prompt_key}/edit", response_class=HTMLResponse)
def prompt_edit_form(
    request: Request,
    prompt_key: StableKey,
) -> Response:
    prompt = prompt_service.get_prompt(
        prompt_key,
        include_deleted=True,
    )
    if prompt["deleted_at"] is not None:
        raise PromptAdminError(
            "prompt_deleted",
            "Deleted Prompt must be restored before editing.",
            409,
        )

    return _render(
        request,
        "prompts/form.html",
        "prompts",
        heading="Edit Prompt",
        submit_label="Save Changes",
        action=f"/prompts/{prompt_key}/edit",
        form={
            **prompt,
            "family_key": prompt["family_key"] or "",
        },
        families=_families(include_deleted=True),
        errors={},
        immutable_key=True,
    )


@router.post("/prompts/{prompt_key}/edit", response_class=HTMLResponse)
async def prompt_edit(
    request: Request,
    prompt_key: StableKey,
) -> Response:
    form = await _read_urlencoded_form(request)
    safe_form = {
        "prompt_key": prompt_key,
        "display_name": form.get("display_name", ""),
        "description": form.get("description", ""),
        "category": form.get("category", ""),
        "family_key": form.get("family_key", ""),
    }
    values = {
        "display_name": safe_form["display_name"],
        "description": safe_form["description"],
        "category": safe_form["category"],
        "family_key": _optional_key(safe_form["family_key"]),
    }

    try:
        data = _model_data(PromptUpdate, values)
        prompt_service.update_prompt(prompt_key, data)
    except ValidationError as exception:
        return _render(
            request,
            "prompts/form.html",
            "prompts",
            status_code=422,
            heading="Edit Prompt",
            submit_label="Save Changes",
            action=f"/prompts/{prompt_key}/edit",
            form=safe_form,
            families=_families(include_deleted=True),
            errors=_field_errors(exception),
            error_summary="Check the highlighted fields.",
            immutable_key=True,
        )
    except PromptAdminError as exception:
        return _render(
            request,
            "prompts/form.html",
            "prompts",
            status_code=exception.status_code,
            heading="Edit Prompt",
            submit_label="Save Changes",
            action=f"/prompts/{prompt_key}/edit",
            form=safe_form,
            families=_families(include_deleted=True),
            errors={},
            error_summary=exception.message,
            immutable_key=True,
        )

    return _redirect(
        f"/prompts/{prompt_key}",
        "prompt-updated",
    )


@router.post("/prompts/{prompt_key}/delete")
def prompt_delete(prompt_key: StableKey) -> RedirectResponse:
    prompt_service.delete_prompt(prompt_key)
    return _redirect(
        f"/prompts/{prompt_key}",
        "prompt-deleted",
    )


@router.post("/prompts/{prompt_key}/restore")
def prompt_restore(prompt_key: StableKey) -> RedirectResponse:
    prompt_service.restore_prompt(prompt_key)
    return _redirect(
        f"/prompts/{prompt_key}",
        "prompt-restored",
    )


@router.get(
    "/prompts/{prompt_key}/variants/new",
    response_class=HTMLResponse,
)
def variant_create_form(
    request: Request,
    prompt_key: StableKey,
) -> Response:
    prompt = prompt_service.get_prompt(prompt_key)
    return _render(
        request,
        "variants/form.html",
        "prompts",
        heading="Create Variant",
        submit_label="Create Variant",
        action=f"/prompts/{prompt_key}/variants",
        prompt=prompt,
        form={
            "variant_key": "",
            "display_name": "",
            "description": "",
            "status": "draft",
        },
        statuses=VARIANT_STATUSES,
        errors={},
        immutable_key=False,
    )


@router.post(
    "/prompts/{prompt_key}/variants",
    response_class=HTMLResponse,
)
async def variant_create(
    request: Request,
    prompt_key: StableKey,
) -> Response:
    prompt = prompt_service.get_prompt(prompt_key)
    form = await _read_urlencoded_form(request)
    safe_form = {
        "variant_key": form.get("variant_key", ""),
        "display_name": form.get("display_name", ""),
        "description": form.get("description", ""),
        "status": form.get("status", "draft"),
    }

    try:
        data = _model_data(VariantCreate, safe_form)
        variant = prompt_service.create_variant(prompt_key, data)
    except ValidationError as exception:
        return _render(
            request,
            "variants/form.html",
            "prompts",
            status_code=422,
            heading="Create Variant",
            submit_label="Create Variant",
            action=f"/prompts/{prompt_key}/variants",
            prompt=prompt,
            form=safe_form,
            statuses=VARIANT_STATUSES,
            errors=_field_errors(exception),
            error_summary="Check the highlighted fields.",
            immutable_key=False,
        )
    except PromptAdminError as exception:
        return _render(
            request,
            "variants/form.html",
            "prompts",
            status_code=exception.status_code,
            heading="Create Variant",
            submit_label="Create Variant",
            action=f"/prompts/{prompt_key}/variants",
            prompt=prompt,
            form=safe_form,
            statuses=VARIANT_STATUSES,
            errors={},
            error_summary=exception.message,
            immutable_key=False,
        )

    return _redirect(
        (
            f"/prompts/{prompt_key}/variants/"
            f"{variant['variant_key']}"
        ),
        "variant-created",
    )


@router.get(
    "/prompts/{prompt_key}/variants/{variant_key}",
    response_class=HTMLResponse,
)
def variant_detail(
    request: Request,
    prompt_key: StableKey,
    variant_key: StableKey,
) -> Response:
    prompt = prompt_service.get_prompt(prompt_key)
    variant = prompt_service.get_variant(prompt_key, variant_key)
    revisions = prompt_service.list_revisions(prompt_key, variant_key)
    return _render(
        request,
        "variants/detail.html",
        "prompts",
        prompt=prompt,
        variant=variant,
        revisions=revisions,
    )


@router.get(
    "/prompts/{prompt_key}/variants/{variant_key}/edit",
    response_class=HTMLResponse,
)
def variant_edit_form(
    request: Request,
    prompt_key: StableKey,
    variant_key: StableKey,
) -> Response:
    prompt = prompt_service.get_prompt(prompt_key)
    variant = prompt_service.get_variant(prompt_key, variant_key)
    return _render(
        request,
        "variants/form.html",
        "prompts",
        heading="Edit Variant",
        submit_label="Save Changes",
        action=(
            f"/prompts/{prompt_key}/variants/"
            f"{variant_key}/edit"
        ),
        prompt=prompt,
        form=variant,
        statuses=VARIANT_STATUSES,
        errors={},
        immutable_key=True,
    )


@router.post(
    "/prompts/{prompt_key}/variants/{variant_key}/edit",
    response_class=HTMLResponse,
)
async def variant_edit(
    request: Request,
    prompt_key: StableKey,
    variant_key: StableKey,
) -> Response:
    prompt = prompt_service.get_prompt(prompt_key)
    form = await _read_urlencoded_form(request)
    safe_form = {
        "variant_key": variant_key,
        "display_name": form.get("display_name", ""),
        "description": form.get("description", ""),
        "status": form.get("status", "draft"),
    }

    try:
        data = _model_data(
            VariantUpdate,
            {
                "display_name": safe_form["display_name"],
                "description": safe_form["description"],
                "status": safe_form["status"],
            },
        )
        prompt_service.update_variant(prompt_key, variant_key, data)
    except ValidationError as exception:
        return _render(
            request,
            "variants/form.html",
            "prompts",
            status_code=422,
            heading="Edit Variant",
            submit_label="Save Changes",
            action=(
                f"/prompts/{prompt_key}/variants/"
                f"{variant_key}/edit"
            ),
            prompt=prompt,
            form=safe_form,
            statuses=VARIANT_STATUSES,
            errors=_field_errors(exception),
            error_summary="Check the highlighted fields.",
            immutable_key=True,
        )
    except PromptAdminError as exception:
        return _render(
            request,
            "variants/form.html",
            "prompts",
            status_code=exception.status_code,
            heading="Edit Variant",
            submit_label="Save Changes",
            action=(
                f"/prompts/{prompt_key}/variants/"
                f"{variant_key}/edit"
            ),
            prompt=prompt,
            form=safe_form,
            statuses=VARIANT_STATUSES,
            errors={},
            error_summary=exception.message,
            immutable_key=True,
        )

    return _redirect(
        f"/prompts/{prompt_key}/variants/{variant_key}",
        "variant-updated",
    )


@router.get(
    "/prompts/{prompt_key}/variants/{variant_key}/revisions/new",
    response_class=HTMLResponse,
)
def revision_create_form(
    request: Request,
    prompt_key: StableKey,
    variant_key: StableKey,
    from_revision: int | None = None,
) -> Response:
    prompt = prompt_service.get_prompt(prompt_key)
    variant = prompt_service.get_variant(prompt_key, variant_key)
    source_revision = None
    if from_revision is not None:
        source_revision = prompt_service.get_revision(
            prompt_key,
            variant_key,
            from_revision,
        )

    return _render(
        request,
        "revisions/form.html",
        "prompts",
        prompt=prompt,
        variant=variant,
        form={
            "system_prompt": (
                source_revision["system_prompt"]
                if source_revision is not None
                else ""
            ),
            "change_note": "",
        },
        errors={},
        source_revision=source_revision,
        can_create=variant["status"] != "archived",
    )


@router.post(
    "/prompts/{prompt_key}/variants/{variant_key}/revisions",
    response_class=HTMLResponse,
)
async def revision_create(
    request: Request,
    prompt_key: StableKey,
    variant_key: StableKey,
) -> Response:
    prompt = prompt_service.get_prompt(prompt_key)
    variant = prompt_service.get_variant(prompt_key, variant_key)
    form = await _read_urlencoded_form(request)
    safe_form = {
        "system_prompt": form.get("system_prompt", ""),
        "change_note": form.get("change_note", ""),
    }

    try:
        data = _model_data(PromptRevisionCreate, safe_form)
        revision = prompt_service.create_revision(
            prompt_key,
            variant_key,
            data,
        )
    except ValidationError as exception:
        return _render(
            request,
            "revisions/form.html",
            "prompts",
            status_code=422,
            prompt=prompt,
            variant=variant,
            form=safe_form,
            errors=_field_errors(exception),
            error_summary="Check the highlighted fields.",
            source_revision=None,
            can_create=variant["status"] != "archived",
        )
    except PromptAdminError as exception:
        return _render(
            request,
            "revisions/form.html",
            "prompts",
            status_code=exception.status_code,
            prompt=prompt,
            variant=variant,
            form=safe_form,
            errors={},
            error_summary=exception.message,
            source_revision=None,
            can_create=variant["status"] != "archived",
        )

    return _redirect(
        (
            f"/prompts/{prompt_key}/variants/{variant_key}/"
            f"revisions/{revision['revision_number']}"
        ),
        "revision-created",
    )


@router.get(
    (
        "/prompts/{prompt_key}/variants/{variant_key}/"
        "revisions/{revision}"
    ),
    response_class=HTMLResponse,
)
def revision_detail(
    request: Request,
    prompt_key: StableKey,
    variant_key: StableKey,
    revision: int = RevisionNumber,
) -> Response:
    prompt = prompt_service.get_prompt(prompt_key)
    variant = prompt_service.get_variant(prompt_key, variant_key)
    revision_item = prompt_service.get_revision(
        prompt_key,
        variant_key,
        revision,
    )
    return _render(
        request,
        "revisions/detail.html",
        "prompts",
        prompt=prompt,
        variant=variant,
        revision=revision_item,
    )


@router.get(
    "/prompts/{prompt_key}/variants/{variant_key}/compare",
    response_class=HTMLResponse,
)
def revision_compare(
    request: Request,
    prompt_key: StableKey,
    variant_key: StableKey,
    from_revision: int | None = None,
    to_revision: int | None = None,
) -> Response:
    prompt = prompt_service.get_prompt(prompt_key)
    variant = prompt_service.get_variant(prompt_key, variant_key)
    revisions = prompt_service.list_revisions(prompt_key, variant_key)
    old_revision = None
    new_revision = None
    unified_lines: list[str] = []
    side_rows: list[DiffRow] = []
    error_summary = None

    if (from_revision is None) != (to_revision is None):
        error_summary = "Choose both Revisions to compare."
    elif from_revision is not None and to_revision is not None:
        try:
            old_revision = prompt_service.get_revision(
                prompt_key,
                variant_key,
                from_revision,
            )
            new_revision = prompt_service.get_revision(
                prompt_key,
                variant_key,
                to_revision,
            )
        except PromptAdminError as exception:
            error_summary = exception.message
        else:
            unified_lines = _unified_diff(
                prompt_key,
                variant_key,
                old_revision,
                new_revision,
            )
            side_rows = _side_by_side_rows(
                old_revision["system_prompt"],
                new_revision["system_prompt"],
            )

    return _render(
        request,
        "revisions/compare.html",
        "prompts",
        prompt=prompt,
        variant=variant,
        revisions=revisions,
        from_revision=from_revision,
        to_revision=to_revision,
        old_revision=old_revision,
        new_revision=new_revision,
        unified_lines=unified_lines,
        side_rows=side_rows,
        error_summary=error_summary,
    )
