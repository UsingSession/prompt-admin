from collections.abc import Callable
from typing import Any

from psycopg import InterfaceError, OperationalError
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation

from db import transaction
from errors import DatabaseUnavailableError, PromptAdminError
from repositories import hook_repository as repository
from schemas.hook import HookCreate, HookRevisionCreate, HookUpdate


UNIQUE_CONSTRAINT_CODES = {
    "ai_hooks_hook_key_unique": "hook_key_conflict",
    "ai_hook_revisions_hook_revision_unique": "hook_revision_conflict",
}
CHECK_CONSTRAINT_CODES = {
    "ai_hook_revisions_hook_group_not_empty": "invalid_hook_group",
    "ai_hook_revisions_hook_group_length": "invalid_hook_group",
    "ai_hook_revisions_priority_non_negative": "invalid_hook_priority",
}


def _not_found(code: str, resource: str) -> PromptAdminError:
    return PromptAdminError(code, f"{resource} was not found.", 404)


def _deleted() -> PromptAdminError:
    return PromptAdminError("hook_deleted", "Hook is deleted.", 409)


def _constraint_name(exception: Exception) -> str | None:
    return getattr(exception.diag, "constraint_name", None)


def _run(operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except PromptAdminError:
        raise
    except UniqueViolation as exception:
        code = UNIQUE_CONSTRAINT_CODES.get(
            _constraint_name(exception),
            "hook_revision_conflict",
        )
        message = (
            "Hook stable key already exists."
            if code == "hook_key_conflict"
            else "Hook Revision already exists."
        )
        raise PromptAdminError(code, message, 409) from exception
    except ForeignKeyViolation as exception:
        raise PromptAdminError(
            "invalid_reference",
            "Referenced resource is invalid.",
            409,
        ) from exception
    except CheckViolation as exception:
        code = CHECK_CONSTRAINT_CODES.get(
            _constraint_name(exception),
            "invalid_reference",
        )
        raise PromptAdminError(
            code,
            "Database constraint rejected the operation.",
            409,
        ) from exception
    except (InterfaceError, OperationalError) as exception:
        raise DatabaseUnavailableError() from exception


def create_hook(data: HookCreate) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            return repository.create_hook(
                cursor,
                data.hook_key,
                data.display_name,
                data.description,
                data.category,
            )

    return _run(operation)


def list_hooks(
    category: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    def operation() -> list[dict]:
        with transaction() as cursor:
            return repository.list_hooks(
                cursor,
                category=category,
                include_deleted=include_deleted,
            )

    return _run(operation)


def get_hook(hook_key: str, include_deleted: bool = False) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            hook = repository.get_hook(
                cursor,
                hook_key,
                include_deleted=include_deleted,
            )
            if hook is None:
                raise _not_found("hook_not_found", "Hook")
            return hook

    return _run(operation)


def update_hook(hook_key: str, data: HookUpdate) -> dict:
    def operation() -> dict:
        values = data.model_dump(exclude_unset=True)
        with transaction() as cursor:
            hook = repository.get_hook_state(cursor, hook_key, lock=True)
            if hook is None:
                raise _not_found("hook_not_found", "Hook")
            if hook["deleted_at"] is not None:
                raise _deleted()
            return repository.update_hook(cursor, hook_key, values)

    return _run(operation)


def delete_hook(hook_key: str) -> None:
    def operation() -> None:
        with transaction() as cursor:
            hook = repository.get_hook_state(cursor, hook_key, lock=True)
            if hook is None:
                raise _not_found("hook_not_found", "Hook")
            if hook["deleted_at"] is not None:
                raise _deleted()
            repository.soft_delete_hook(cursor, hook_key)

    _run(operation)


def restore_hook(hook_key: str) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            hook = repository.get_hook_state(cursor, hook_key, lock=True)
            if hook is None:
                raise _not_found("hook_not_found", "Hook")
            if hook["deleted_at"] is None:
                return repository.get_hook(cursor, hook_key)
            return repository.restore_hook(cursor, hook_key)

    return _run(operation)


def create_revision(hook_key: str, data: HookRevisionCreate) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            hook = repository.get_hook_state(cursor, hook_key, lock=True)
            if hook is None:
                raise _not_found("hook_not_found", "Hook")
            if hook["deleted_at"] is not None:
                raise _deleted()
            revision_number = repository.next_hook_revision_number(
                cursor,
                hook["id"],
            )
            return repository.create_revision(
                cursor,
                hook["id"],
                revision_number,
                data.hook_group,
                data.hook_content,
                data.priority,
                data.is_enabled,
                data.change_note,
            )

    return _run(operation)


def list_revisions(hook_key: str) -> list[dict]:
    def operation() -> list[dict]:
        with transaction() as cursor:
            hook = repository.get_hook_state(cursor, hook_key)
            if hook is None:
                raise _not_found("hook_not_found", "Hook")
            if hook["deleted_at"] is not None:
                raise _deleted()
            return repository.list_revisions(cursor, hook_key)

    return _run(operation)


def get_revision(hook_key: str, revision_number: int) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            hook = repository.get_hook_state(cursor, hook_key)
            if hook is None:
                raise _not_found("hook_not_found", "Hook")
            if hook["deleted_at"] is not None:
                raise _deleted()
            revision = repository.get_revision(
                cursor,
                hook_key,
                revision_number,
            )
            if revision is None:
                raise _not_found(
                    "hook_revision_not_found",
                    "Hook Revision",
                )
            return revision

    return _run(operation)
