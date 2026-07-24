from http import HTTPStatus

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.hook_management import router as hook_management_router
from api.prompt_compilation import router as prompt_compilation_router
from api.prompt_management import router as prompt_management_router
from db import db_health_check
from ui.deleted_records import router as deleted_records_ui_router
from ui.hook_management import router as hook_management_ui_router
from ui.prompt_management import router as prompt_management_ui_router


router = APIRouter()
router.include_router(prompt_management_ui_router)
router.include_router(hook_management_ui_router)
router.include_router(deleted_records_ui_router)
router.include_router(prompt_management_router)
router.include_router(hook_management_router)
router.include_router(prompt_compilation_router)


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
