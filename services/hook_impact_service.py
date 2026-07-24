from psycopg import InterfaceError, OperationalError

from db import transaction
from errors import DatabaseUnavailableError, PromptAdminError
from repositories import (
    hook_repository,
    hook_ui_repository,
    prompt_reference_repository,
)
from services.compiler import parse_hook_groups


def _contribution_state(hook: dict, revision: dict | None) -> str:
    if revision is None:
        return "no_revision"
    if hook["deleted_at"] is not None:
        return "deleted"
    if not revision["is_enabled"]:
        return "disabled"
    return "enabled"


def get_hook_impact(hook_key: str) -> dict:
    try:
        with transaction() as cursor:
            hook = hook_ui_repository.get_hook_summary(cursor, hook_key)
            if hook is None:
                raise PromptAdminError(
                    "hook_not_found",
                    "Hook was not found.",
                    404,
                )

            revisions = hook_repository.list_revisions(cursor, hook_key)
            revision = revisions[-1] if revisions else None
            state = _contribution_state(hook, revision)
            if revision is None:
                return {
                    "hook": hook,
                    "revision": None,
                    "contribution_state": state,
                    "group_hooks": [],
                    "prompt_references": [],
                }

            hook_group = revision["hook_group"]
            group_hooks = hook_ui_repository.list_group_latest_revisions(
                cursor,
                hook_group,
            )
            for item in group_hooks:
                item["is_selected"] = item["hook_key"] == hook_key
                item["contributes"] = (
                    item["deleted_at"] is None and item["is_enabled"]
                )

            placeholder = f"#{hook_group}"
            candidates = (
                prompt_reference_repository.list_prompt_revision_candidates(
                    cursor,
                    placeholder,
                )
            )
            prompt_references = []
            for candidate in candidates:
                if hook_group not in parse_hook_groups(
                    candidate["system_prompt"]
                ):
                    continue
                reference = dict(candidate)
                reference.pop("system_prompt")
                prompt_references.append(reference)

            return {
                "hook": hook,
                "revision": revision,
                "contribution_state": state,
                "group_hooks": group_hooks,
                "prompt_references": prompt_references,
            }
    except PromptAdminError:
        raise
    except (InterfaceError, OperationalError) as exception:
        raise DatabaseUnavailableError() from exception
