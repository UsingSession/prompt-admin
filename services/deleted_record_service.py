from collections.abc import Callable
from typing import Any

from psycopg import InterfaceError, OperationalError
from psycopg.errors import ForeignKeyViolation

from db import transaction
from errors import DatabaseUnavailableError, PromptAdminError
from repositories import deleted_record_repository as repository
from repositories import prompt_repository


def _not_found(code: str, resource: str) -> PromptAdminError:
    return PromptAdminError(code, f"{resource} was not found.", 404)


def _run(operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except PromptAdminError:
        raise
    except ForeignKeyViolation as exception:
        raise PromptAdminError(
            "permanent_delete_blocked",
            "The record is still referenced and cannot be deleted permanently.",
            409,
        ) from exception
    except (InterfaceError, OperationalError) as exception:
        raise DatabaseUnavailableError() from exception


def permanently_delete_family(family_key: str) -> None:
    """Delete one soft-deleted Family and detach associated Prompts."""

    def operation() -> None:
        with transaction() as cursor:
            family = prompt_repository.get_family(
                cursor,
                family_key,
                include_deleted=True,
                lock=True,
            )
            if family is None:
                raise _not_found("family_not_found", "Family")
            if family["deleted_at"] is None:
                raise PromptAdminError(
                    "family_not_deleted",
                    "Family must be soft-deleted first.",
                    409,
                )
            repository.permanently_delete_family(cursor, family_key)

    _run(operation)


def permanently_delete_prompt(prompt_key: str) -> None:
    """Delete one soft-deleted Prompt and its unreferenced history."""

    def operation() -> None:
        with transaction() as cursor:
            prompt = prompt_repository.get_prompt_state(
                cursor,
                prompt_key,
                lock=True,
            )
            if prompt is None:
                raise _not_found("prompt_not_found", "Prompt")
            if prompt["deleted_at"] is None:
                raise PromptAdminError(
                    "prompt_not_deleted",
                    "Prompt must be soft-deleted first.",
                    409,
                )
            if repository.prompt_has_referenced_revisions(
                cursor,
                prompt["id"],
            ):
                raise PromptAdminError(
                    "permanent_delete_blocked",
                    "Prompt Revisions are referenced by a Bundle item.",
                    409,
                )
            repository.permanently_delete_prompt(cursor, prompt["id"])

    _run(operation)
