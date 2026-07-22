import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import SETTINGS, STATIC_DIR, TEMPLATES_DIR, Settings
from db import init_database
from errors import PromptAdminError
from routes import router


LOGGER = logging.getLogger("prompt_admin")
TEMPLATES = Jinja2Templates(directory=str(TEMPLATES_DIR))


ERROR_CODES = {
    400: "bad_request",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_failed",
    500: "internal_error",
    503: "service_unavailable",
}


def error_code(status_code: int) -> str:
    return ERROR_CODES.get(status_code, "http_error")


def error_message(detail: Any, status_code: int) -> str:
    if isinstance(detail, str) and detail:
        return detail
    if status_code == 404:
        return "Resource not found."
    if status_code == 500:
        return "Request failed."
    return "Request could not be completed."


def error_response(
    request: Request,
    status_code: int,
    message: str,
) -> Response:
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            {
                "error": {
                    "code": error_code(status_code),
                    "message": message,
                }
            },
            status_code=status_code,
        )

    return TEMPLATES.TemplateResponse(
        request=request,
        name="http_error.html",
        context={
            "status_code": status_code,
            "title": error_code(status_code).replace("_", " ").title(),
            "message": message,
        },
        status_code=status_code,
    )


def create_app(
    settings: Settings | None = None,
    initialize_database: bool = True,
) -> FastAPI:
    resolved_settings = settings or SETTINGS

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if initialize_database:
            init_database()
        yield

    application = FastAPI(
        title="Prompt Admin",
        version="2.0.0-dev",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.templates = TEMPLATES
    application.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )
    application.include_router(router)

    @application.exception_handler(PromptAdminError)
    async def prompt_admin_error_handler(
        request: Request,
        exception: PromptAdminError,
    ) -> Response:
        return error_response(request, 400, str(exception))

    @application.exception_handler(ValueError)
    async def value_error_handler(
        request: Request,
        exception: ValueError,
    ) -> Response:
        return error_response(request, 400, str(exception))

    @application.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        _: RequestValidationError,
    ) -> Response:
        return error_response(request, 422, "Request validation failed.")

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request,
        exception: StarletteHTTPException,
    ) -> Response:
        return error_response(
            request,
            exception.status_code,
            error_message(exception.detail, exception.status_code),
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request,
        exception: Exception,
    ) -> Response:
        LOGGER.error(
            "Unhandled request error",
            exc_info=(
                type(exception),
                exception,
                exception.__traceback__,
            ),
        )
        return error_response(request, 500, "Request failed.")

    return application


app = create_app()
