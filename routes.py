from http import HTTPStatus

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from db import db_health_check


router = APIRouter()
LEGACY_DOMAIN_MESSAGE = (
    "Prompt Admin v2 domain routes are temporarily unavailable during the "
    "database schema transition."
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
def legacy_compiled_prompts() -> JSONResponse:
    return JSONResponse(
        {
            "error": {
                "code": "legacy_domain_unavailable",
                "message": LEGACY_DOMAIN_MESSAGE,
            }
        },
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
    )


def legacy_ui_unavailable(request: Request) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="http_error.html",
        context={
            "status_code": HTTPStatus.SERVICE_UNAVAILABLE,
            "title": "Service Unavailable",
            "message": LEGACY_DOMAIN_MESSAGE,
        },
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
    )


LEGACY_UI_ROUTES = {
    "/": ("GET",),
    "/api-docs": ("GET",),
    "/new": ("GET",),
    "/edit": ("GET",),
    "/clone": ("GET",),
    "/preview": ("GET",),
    "/confirm-delete": ("GET",),
    "/history": ("GET",),
    "/families": ("GET",),
    "/family": ("GET",),
    "/family-new": ("GET",),
    "/family-edit": ("GET",),
    "/family-confirm-delete": ("GET",),
    "/hooks": ("GET",),
    "/hook-new": ("GET",),
    "/hook-edit": ("GET",),
    "/hook-clone": ("GET",),
    "/hook-confirm-delete": ("GET",),
    "/hook-history": ("GET",),
    "/deleted": ("GET",),
    "/download": ("GET",),
    "/export": ("GET",),
    "/import": ("GET", "POST"),
    "/save": ("POST",),
    "/validate": ("POST",),
    "/delete": ("POST",),
    "/purge": ("POST",),
    "/restore": ("POST",),
    "/family-save": ("POST",),
    "/family-delete": ("POST",),
    "/family-purge": ("POST",),
    "/family-restore": ("POST",),
    "/hook-save": ("POST",),
    "/hook-validate": ("POST",),
    "/hook-delete": ("POST",),
    "/hook-purge": ("POST",),
    "/hook-restore": ("POST",),
}

for route_path, route_methods in LEGACY_UI_ROUTES.items():
    route_name = "legacy_" + (route_path.strip("/") or "index")
    router.add_api_route(
        route_path,
        legacy_ui_unavailable,
        methods=list(route_methods),
        name=route_name.replace("-", "_"),
        response_class=HTMLResponse,
        include_in_schema=False,
    )
