from http import HTTPStatus

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.prompt_management import router as prompt_management_router
from db import db_health_check


router = APIRouter()
router.include_router(prompt_management_router)


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
