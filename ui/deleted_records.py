from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from schemas.prompt import StableKey
from services import deleted_record_service, hook_service, prompt_service


router = APIRouter(include_in_schema=False)
STATUS_MESSAGES = {
    "family-permanently-deleted": "Family permanently deleted.",
    "prompt-permanently-deleted": "Prompt permanently deleted.",
}


def _render(
    request: Request,
    status_code: int = 200,
    error_message: str | None = None,
) -> Response:
    deleted_families = [
        family
        for family in prompt_service.list_families(include_deleted=True)
        if family["deleted_at"] is not None
    ]
    deleted_prompts = [
        prompt
        for prompt in prompt_service.list_prompts(include_deleted=True)
        if prompt["deleted_at"] is not None
    ]
    deleted_hooks = [
        hook
        for hook in hook_service.list_hooks(include_deleted=True)
        if hook["deleted_at"] is not None
    ]
    prompt_counts = {
        family["family_key"]: len(
            prompt_service.list_prompts(
                family_key=family["family_key"],
                include_deleted=True,
            )
        )
        for family in deleted_families
    }
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="deleted/list.html",
        context={
            "request": request,
            "active_nav": "deleted",
            "status_message": STATUS_MESSAGES.get(
                request.query_params.get("status", "")
            ),
            "error_message": error_message,
            "families": deleted_families,
            "prompts": deleted_prompts,
            "hooks": deleted_hooks,
            "prompt_counts": prompt_counts,
        },
        status_code=status_code,
    )


def _redirect(status: str) -> RedirectResponse:
    return RedirectResponse(
        f"/deleted?{urlencode({'status': status})}",
        status_code=303,
    )


@router.get("/deleted", response_class=HTMLResponse)
def deleted_records(request: Request) -> Response:
    return _render(request)


@router.post("/deleted/families/{family_key}/permanent-delete")
def permanently_delete_family(
    family_key: StableKey,
) -> RedirectResponse:
    deleted_record_service.permanently_delete_family(family_key)
    return _redirect("family-permanently-deleted")


@router.post("/deleted/prompts/{prompt_key}/permanent-delete")
def permanently_delete_prompt(
    prompt_key: StableKey,
) -> RedirectResponse:
    deleted_record_service.permanently_delete_prompt(prompt_key)
    return _redirect("prompt-permanently-deleted")
