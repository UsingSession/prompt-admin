import logging
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

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
LOCAL_POST_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


ERROR_CODES = {
    400: "bad_request",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_failed",
    500: "internal_error",
    503: "service_unavailable",
}
VALIDATION_FIELD_CODES = {
    "hook_group": "invalid_hook_group",
    "priority": "invalid_hook_priority",
    "status": "invalid_variant_status",
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


def is_local_request_source(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False

    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname in LOCAL_POST_HOSTS
    )


def error_response(
    request: Request,
    status_code: int,
    message: str,
    code: str | None = None,
) -> Response:
    resolved_code = code or error_code(status_code)
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            {
                "error": {
                    "code": resolved_code,
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
            "title": resolved_code.replace("_", " ").title(),
            "message": message,
        },
        status_code=status_code,
    )


def validation_error_code(exception: RequestValidationError) -> str:
    for error in exception.errors():
        location = error.get("loc", ())
        if not location:
            continue
        code = VALIDATION_FIELD_CODES.get(location[-1])
        if code is not None:
            return code
    return "validation_failed"


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

    @application.middleware("http")
    async def apply_common_http_policy(request: Request, call_next):
        response: Response
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            source = (
                request.headers.get("Origin")
                or request.headers.get("Referer")
                or ""
            )
            if source and not is_local_request_source(source):
                response = error_response(
                    request,
                    403,
                    "Cross-site requests are not allowed.",
                )
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)

        response.headers.setdefault("Cache-Control", "no-cache")
        return response

    @application.exception_handler(PromptAdminError)
    async def prompt_admin_error_handler(
        request: Request,
        exception: PromptAdminError,
    ) -> Response:
        return error_response(
            request,
            exception.status_code,
            exception.message,
            exception.code,
        )

    @application.exception_handler(ValueError)
    async def value_error_handler(
        request: Request,
        exception: ValueError,
    ) -> Response:
        return error_response(request, 400, str(exception))

    @application.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        exception: RequestValidationError,
    ) -> Response:
        return error_response(
            request,
            422,
            "Request validation failed.",
            validation_error_code(exception),
        )

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
