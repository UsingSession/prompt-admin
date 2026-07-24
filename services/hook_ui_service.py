from collections.abc import Callable
from typing import Any

from psycopg import InterfaceError, OperationalError

from db import transaction
from errors import DatabaseUnavailableError, PromptAdminError
from repositories import hook_repository, hook_ui_repository


def _run(operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except PromptAdminError:
        raise
    except (InterfaceError, OperationalError) as exception:
        raise DatabaseUnavailableError() from exception


def _not_found(code: str, resource: str) -> PromptAdminError:
    return PromptAdminError(code, f"{resource} was not found.", 404)


def list_hook_summaries(
    category: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    def operation() -> list[dict]:
        with transaction() as cursor:
            return hook_ui_repository.list_hook_summaries(
                cursor,
                category=category,
                include_deleted=include_deleted,
            )

    return _run(operation)


def dashboard_summary() -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            return hook_ui_repository.dashboard_counts(cursor)

    return _run(operation)


def get_hook_detail(hook_key: str) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            hook = hook_ui_repository.get_hook_summary(cursor, hook_key)
            if hook is None:
                raise _not_found("hook_not_found", "Hook")
            return {
                "hook": hook,
                "revisions": hook_repository.list_revisions(cursor, hook_key),
            }

    return _run(operation)


def get_revision(hook_key: str, revision_number: int) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            hook = hook_ui_repository.get_hook_summary(cursor, hook_key)
            if hook is None:
                raise _not_found("hook_not_found", "Hook")
            revision = hook_repository.get_revision(
                cursor,
                hook_key,
                revision_number,
            )
            if revision is None:
                raise _not_found(
                    "hook_revision_not_found",
                    "Hook Revision",
                )
            return {"hook": hook, "revision": revision}

    return _run(operation)
