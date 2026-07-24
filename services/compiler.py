import re
from collections.abc import Sequence

from psycopg import Cursor, InterfaceError, OperationalError

from db import transaction
from errors import DatabaseUnavailableError, PromptAdminError
from repositories import hook_repository, prompt_repository
from schemas.compiler import CompilationMode


HOOK_PATTERN = re.compile(r"#(hook_[A-Za-z0-9_.-]+)")
HOOK_SEPARATOR = "\n\n"


def parse_hook_groups(raw_prompt: str) -> list[str]:
    """Return unique Hook groups in first-occurrence order."""
    groups = []
    seen = set()
    for match in HOOK_PATTERN.finditer(raw_prompt):
        group = match.group(1)
        if group not in seen:
            seen.add(group)
            groups.append(group)
    return groups


def compile_resolved_prompt(
    raw_prompt: str,
    mode: CompilationMode,
    resolved_hooks: Sequence[dict],
) -> dict:
    detected_groups = parse_hook_groups(raw_prompt)
    content_by_group: dict[str, list[str]] = {
        group: [] for group in detected_groups
    }
    for hook in resolved_hooks:
        group = hook["hook_group"]
        if group in content_by_group:
            content_by_group[group].append(hook["hook_content"])

    unresolved_groups = [
        group for group in detected_groups if not content_by_group[group]
    ]
    if mode == "strict" and unresolved_groups:
        raise PromptAdminError(
            "unresolved_hook_groups",
            "Prompt contains unresolved Hook groups.",
            422,
        )

    def replace_placeholder(match: re.Match) -> str:
        group = match.group(1)
        contents = content_by_group.get(group, [])
        if not contents:
            return match.group(0)
        return HOOK_SEPARATOR.join(contents)

    compiled_prompt = HOOK_PATTERN.sub(replace_placeholder, raw_prompt)
    metadata = [
        {
            "hook_key": hook["hook_key"],
            "revision_number": hook["revision_number"],
            "hook_group": hook["hook_group"],
            "priority": hook["priority"],
        }
        for hook in resolved_hooks
        if hook["hook_group"] in detected_groups
    ]
    return {
        "mode": mode,
        "raw_prompt": raw_prompt,
        "compiled_prompt": compiled_prompt,
        "detected_groups": detected_groups,
        "resolved_hooks": metadata,
        "unresolved_groups": unresolved_groups,
    }


def compile_with_cursor(
    cursor: Cursor,
    raw_prompt: str,
    mode: CompilationMode,
) -> dict:
    """Compile through a caller-owned PostgreSQL transaction cursor."""
    detected_groups = parse_hook_groups(raw_prompt)
    resolved_hooks = hook_repository.load_effective_hook_revisions(
        cursor,
        detected_groups,
    )
    return compile_resolved_prompt(raw_prompt, mode, resolved_hooks)


def preview_prompt_revision(
    prompt_key: str,
    variant_key: str,
    revision_number: int,
) -> dict:
    try:
        with transaction() as cursor:
            prompt = prompt_repository.get_prompt_state(cursor, prompt_key)
            if prompt is None:
                raise PromptAdminError(
                    "prompt_not_found",
                    "Prompt was not found.",
                    404,
                )
            if prompt["deleted_at"] is not None:
                raise PromptAdminError(
                    "prompt_deleted",
                    "Prompt is deleted.",
                    409,
                )
            variant = prompt_repository.get_variant(
                cursor,
                prompt_key,
                variant_key,
            )
            if variant is None:
                raise PromptAdminError(
                    "variant_not_found",
                    "Variant was not found.",
                    404,
                )
            revision = prompt_repository.get_revision(
                cursor,
                prompt_key,
                variant_key,
                revision_number,
            )
            if revision is None:
                raise PromptAdminError(
                    "revision_not_found",
                    "Revision was not found.",
                    404,
                )
            return compile_with_cursor(
                cursor,
                revision["system_prompt"],
                "preview",
            )
    except PromptAdminError:
        raise
    except (InterfaceError, OperationalError) as exception:
        raise DatabaseUnavailableError() from exception
