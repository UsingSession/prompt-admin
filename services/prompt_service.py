from collections.abc import Callable
from typing import Any

from psycopg import InterfaceError, OperationalError
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation

from db import transaction
from errors import DatabaseUnavailableError, PromptAdminError
from repositories import prompt_repository as repository
from schemas.prompt import (
    FamilyCreate,
    FamilyUpdate,
    PromptCreate,
    PromptRevisionCreate,
    PromptUpdate,
    VariantCreate,
    VariantUpdate,
)


UNIQUE_CONSTRAINT_CODES = {
    "ai_prompt_families_family_key_unique": "family_key_conflict",
    "ai_prompts_prompt_key_unique": "prompt_key_conflict",
    "ai_prompt_variants_prompt_variant_unique": "variant_key_conflict",
    "ai_prompt_revisions_variant_revision_unique": "revision_conflict",
}


def _not_found(code: str, resource: str) -> PromptAdminError:
    return PromptAdminError(code, f"{resource} was not found.", 404)


def _deleted(code: str, resource: str) -> PromptAdminError:
    return PromptAdminError(code, f"{resource} is deleted.", 409)


def _constraint_name(exception: UniqueViolation) -> str | None:
    return getattr(exception.diag, "constraint_name", None)


def _run(operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except PromptAdminError:
        raise
    except UniqueViolation as exception:
        code = UNIQUE_CONSTRAINT_CODES.get(
            _constraint_name(exception),
            "conflict",
        )
        raise PromptAdminError(
            code,
            "Stable key already exists.",
            409,
        ) from exception
    except ForeignKeyViolation as exception:
        raise PromptAdminError(
            "invalid_reference",
            "Referenced resource is invalid.",
            409,
        ) from exception
    except CheckViolation as exception:
        raise PromptAdminError(
            "invalid_reference",
            "Database constraint rejected the operation.",
            409,
        ) from exception
    except (InterfaceError, OperationalError) as exception:
        raise DatabaseUnavailableError() from exception


def create_family(data: FamilyCreate) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            return repository.create_family(
                cursor,
                data.family_key,
                data.display_name,
                data.description,
            )

    return _run(operation)


def list_families(include_deleted: bool = False) -> list[dict]:
    return _run(
        lambda: _read(
            lambda cursor: repository.list_families(cursor, include_deleted)
        )
    )


def get_family(family_key: str, include_deleted: bool = False) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            family = repository.get_family(
                cursor,
                family_key,
                include_deleted=include_deleted,
            )
            if family is None:
                raise _not_found("family_not_found", "Family")
            return family

    return _run(operation)


def update_family(family_key: str, data: FamilyUpdate) -> dict:
    def operation() -> dict:
        values = data.model_dump(exclude_unset=True)
        with transaction() as cursor:
            family = repository.get_family(
                cursor,
                family_key,
                include_deleted=True,
                lock=True,
            )
            if family is None:
                raise _not_found("family_not_found", "Family")
            if family["deleted_at"] is not None:
                raise _deleted("family_deleted", "Family")
            return repository.update_family(cursor, family_key, values)

    return _run(operation)


def delete_family(family_key: str) -> None:
    def operation() -> None:
        with transaction() as cursor:
            family = repository.get_family(
                cursor,
                family_key,
                include_deleted=True,
                lock=True,
            )
            if family is None:
                raise _not_found("family_not_found", "Family")
            if family["deleted_at"] is not None:
                raise _deleted("family_deleted", "Family")
            repository.soft_delete_family(cursor, family_key)

    _run(operation)


def restore_family(family_key: str) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            family = repository.get_family(
                cursor,
                family_key,
                include_deleted=True,
                lock=True,
            )
            if family is None:
                raise _not_found("family_not_found", "Family")
            if family["deleted_at"] is None:
                return family
            return repository.restore_family(cursor, family_key)

    return _run(operation)


def _family_id(cursor, family_key: str | None) -> int | None:
    if family_key is None:
        return None
    family = repository.get_family_id(cursor, family_key, lock=True)
    if family is None:
        raise PromptAdminError(
            "invalid_reference",
            "Referenced Family was not found.",
            409,
        )
    if family["deleted_at"] is not None:
        raise _deleted("family_deleted", "Family")
    return family["id"]


def create_prompt(data: PromptCreate) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            family_id = _family_id(cursor, data.family_key)
            return repository.create_prompt(
                cursor,
                data.prompt_key,
                data.display_name,
                data.description,
                data.category,
                family_id,
            )

    return _run(operation)


def list_prompts(
    family_key: str | None = None,
    category: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    return _run(
        lambda: _read(
            lambda cursor: repository.list_prompts(
                cursor,
                family_key=family_key,
                category=category,
                include_deleted=include_deleted,
            )
        )
    )


def get_prompt(prompt_key: str, include_deleted: bool = False) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            prompt = repository.get_prompt(
                cursor,
                prompt_key,
                include_deleted=include_deleted,
            )
            if prompt is None:
                raise _not_found("prompt_not_found", "Prompt")
            return prompt

    return _run(operation)


def update_prompt(prompt_key: str, data: PromptUpdate) -> dict:
    def operation() -> dict:
        values = data.model_dump(exclude_unset=True)
        with transaction() as cursor:
            prompt = repository.get_prompt_state(cursor, prompt_key, lock=True)
            if prompt is None:
                raise _not_found("prompt_not_found", "Prompt")
            if prompt["deleted_at"] is not None:
                raise _deleted("prompt_deleted", "Prompt")
            if "family_key" in values:
                values["prompt_family_id"] = _family_id(
                    cursor,
                    values.pop("family_key"),
                )
            return repository.update_prompt(cursor, prompt_key, values)

    return _run(operation)


def delete_prompt(prompt_key: str) -> None:
    def operation() -> None:
        with transaction() as cursor:
            prompt = repository.get_prompt_state(cursor, prompt_key, lock=True)
            if prompt is None:
                raise _not_found("prompt_not_found", "Prompt")
            if prompt["deleted_at"] is not None:
                raise _deleted("prompt_deleted", "Prompt")
            repository.soft_delete_prompt(cursor, prompt_key)

    _run(operation)


def restore_prompt(prompt_key: str) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            prompt = repository.get_prompt_state(cursor, prompt_key, lock=True)
            if prompt is None:
                raise _not_found("prompt_not_found", "Prompt")
            if prompt["deleted_at"] is None:
                return repository.get_prompt(cursor, prompt_key)
            return repository.restore_prompt(cursor, prompt_key)

    return _run(operation)


def _active_prompt(cursor, prompt_key: str, lock: bool = False) -> dict:
    prompt = repository.get_prompt_state(cursor, prompt_key, lock=lock)
    if prompt is None:
        raise _not_found("prompt_not_found", "Prompt")
    if prompt["deleted_at"] is not None:
        raise _deleted("prompt_deleted", "Prompt")
    return prompt


def create_variant(prompt_key: str, data: VariantCreate) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            prompt = _active_prompt(cursor, prompt_key, lock=True)
            return repository.create_variant(
                cursor,
                prompt["id"],
                data.variant_key,
                data.display_name,
                data.description,
                data.status,
            )

    return _run(operation)


def list_variants(prompt_key: str) -> list[dict]:
    def operation() -> list[dict]:
        with transaction() as cursor:
            _active_prompt(cursor, prompt_key)
            return repository.list_variants(cursor, prompt_key)

    return _run(operation)


def get_variant(prompt_key: str, variant_key: str) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            _active_prompt(cursor, prompt_key)
            variant = repository.get_variant(cursor, prompt_key, variant_key)
            if variant is None:
                raise _not_found("variant_not_found", "Variant")
            return variant

    return _run(operation)


def update_variant(
    prompt_key: str,
    variant_key: str,
    data: VariantUpdate,
) -> dict:
    def operation() -> dict:
        values = data.model_dump(exclude_unset=True)
        with transaction() as cursor:
            prompt = _active_prompt(cursor, prompt_key, lock=True)
            variant = repository.get_variant_state(
                cursor,
                prompt["id"],
                variant_key,
                lock=True,
            )
            if variant is None or variant["deleted_at"] is not None:
                raise _not_found("variant_not_found", "Variant")
            return repository.update_variant(
                cursor,
                prompt["id"],
                variant_key,
                values,
            )

    return _run(operation)


def create_revision(
    prompt_key: str,
    variant_key: str,
    data: PromptRevisionCreate,
) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            prompt = _active_prompt(cursor, prompt_key, lock=True)
            variant = repository.get_variant_state(
                cursor,
                prompt["id"],
                variant_key,
                lock=True,
            )
            if variant is None or variant["deleted_at"] is not None:
                raise _not_found("variant_not_found", "Variant")
            if variant["status"] == "archived":
                raise PromptAdminError(
                    "variant_archived",
                    "Archived Variant cannot receive new revisions.",
                    409,
                )
            revision_number = repository.next_prompt_revision_number(
                cursor,
                variant["id"],
            )
            return repository.create_revision(
                cursor,
                variant["id"],
                revision_number,
                data.system_prompt,
                data.change_note,
            )

    return _run(operation)


def list_revisions(prompt_key: str, variant_key: str) -> list[dict]:
    def operation() -> list[dict]:
        with transaction() as cursor:
            _active_prompt(cursor, prompt_key)
            variant = repository.get_variant(cursor, prompt_key, variant_key)
            if variant is None:
                raise _not_found("variant_not_found", "Variant")
            return repository.list_revisions(cursor, prompt_key, variant_key)

    return _run(operation)


def get_revision(
    prompt_key: str,
    variant_key: str,
    revision_number: int,
) -> dict:
    def operation() -> dict:
        with transaction() as cursor:
            _active_prompt(cursor, prompt_key)
            variant = repository.get_variant(cursor, prompt_key, variant_key)
            if variant is None:
                raise _not_found("variant_not_found", "Variant")
            revision = repository.get_revision(
                cursor,
                prompt_key,
                variant_key,
                revision_number,
            )
            if revision is None:
                raise _not_found("revision_not_found", "Revision")
            return revision

    return _run(operation)


def _read(operation: Callable[[Any], Any]) -> Any:
    with transaction() as cursor:
        return operation(cursor)
