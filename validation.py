from errors import PromptAdminError


ALLOWED_KEY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-."
HOOK_GROUP_PREFIX = "hook_"


def validate_key(value):
    prompt_key = (value or "").strip()

    if not prompt_key:
        raise PromptAdminError("Key is required.")
    if len(prompt_key) > 120:
        raise PromptAdminError("Key must be 120 characters or fewer.")
    if any(char not in ALLOWED_KEY_CHARS for char in prompt_key):
        raise PromptAdminError(
            "Key may contain only letters, numbers, underscore, dash, and dot."
        )

    return prompt_key


def normalize_hook_group(value):
    hook_group = validate_key(value)
    if hook_group.startswith(HOOK_GROUP_PREFIX):
        return hook_group
    return f"{HOOK_GROUP_PREFIX}{hook_group}"


def hook_group_suffix(value):
    hook_group = value or ""
    if hook_group.startswith(HOOK_GROUP_PREFIX):
        return hook_group.removeprefix(HOOK_GROUP_PREFIX)
    return hook_group


def validate_prompt_text(system_prompt):
    warnings = []
    text = system_prompt or ""
    stripped = text.strip()

    if not stripped:
        warnings.append("Prompt is empty.")
    if stripped and len(stripped) < 80:
        warnings.append("Prompt is very short. Confirm that this is intentional.")
    if "#hook_" in text:
        warnings.append("Prompt contains hook placeholders. Use compiled preview to verify them.")
    if "Output" not in text and "output" not in text:
        warnings.append("Prompt does not mention expected output format.")

    return warnings


def validate_hook_text(hook_content):
    warnings = []
    text = hook_content or ""
    stripped = text.strip()

    if not stripped:
        warnings.append("Hook is empty.")
    if "#hook_" in text:
        warnings.append("Hook content should not contain hook placeholders.")

    return warnings


def validate_family_items(families):
    if not isinstance(families, list):
        raise PromptAdminError("families must be an array.")
    for index, family in enumerate(families, start=1):
        if not isinstance(family, dict):
            raise PromptAdminError(f"Family item #{index} must be an object.")
        validate_key(family.get("family_key", ""))


def has_import_value(item, key):
    return key in item and item.get(key) not in (None, "")


def validate_prompt_family_import_fields(prompt, index):
    has_family_key = has_import_value(prompt, "prompt_family_key")
    has_family_version = has_import_value(prompt, "family_version")

    if has_family_key != has_family_version:
        raise PromptAdminError(
            f"Prompt item #{index} must provide prompt_family_key and family_version together."
        )

    if not has_family_key:
        return

    validate_key(prompt.get("prompt_family_key", ""))
    try:
        family_version = int(prompt.get("family_version"))
    except (TypeError, ValueError) as exc:
        raise PromptAdminError(
            f"Prompt item #{index} family_version must be a positive integer."
        ) from exc

    if family_version < 1:
        raise PromptAdminError(
            f"Prompt item #{index} family_version must be a positive integer."
        )


def validate_prompt_items(prompts):
    if not isinstance(prompts, list):
        raise PromptAdminError("prompts must be an array.")
    for index, prompt in enumerate(prompts, start=1):
        if not isinstance(prompt, dict):
            raise PromptAdminError(f"Prompt item #{index} must be an object.")
        validate_key(prompt.get("prompt_key", ""))
        validate_prompt_family_import_fields(prompt, index)
        if "system_prompt" not in prompt:
            raise PromptAdminError(f"Prompt item #{index} is missing system_prompt.")


def validate_hook_items(hooks):
    if not isinstance(hooks, list):
        raise PromptAdminError("hooks must be an array.")
    for index, hook in enumerate(hooks, start=1):
        if not isinstance(hook, dict):
            raise PromptAdminError(f"Hook item #{index} must be an object.")
        validate_key(hook.get("hook_key", ""))
        normalize_hook_group(hook.get("hook_group", ""))
        if "hook_content" not in hook:
            raise PromptAdminError(f"Hook item #{index} is missing hook_content.")


def validate_import_payload(payload):
    if not isinstance(payload, dict):
        raise PromptAdminError("Import payload must be a JSON object.")

    families = payload.get("families", [])
    prompts = payload.get("prompts", [])
    hooks = payload.get("hooks", [])

    validate_family_items(families)
    validate_prompt_items(prompts)
    validate_hook_items(hooks)

    return {"families": families, "prompts": prompts, "hooks": hooks}
