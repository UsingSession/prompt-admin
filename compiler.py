import re

from hook_repository import list_active_hooks_by_group


HOOK_PATTERN = re.compile(r"#(hook_[A-Za-z0-9_.-]+)")


def find_hook_groups(system_prompt):
    groups = []
    for match in HOOK_PATTERN.finditer(system_prompt or ""):
        group = match.group(1)
        if group not in groups:
            groups.append(group)
    return groups


def compile_prompt_text(system_prompt):
    system_prompt = system_prompt or ""
    groups = find_hook_groups(system_prompt)
    resolved_hooks = []
    unresolved_groups = []

    def replace_placeholder(match):
        hook_group = match.group(1)
        hooks = list_active_hooks_by_group(hook_group)
        if not hooks:
            if hook_group not in unresolved_groups:
                unresolved_groups.append(hook_group)
            return ""

        resolved_hooks.extend(hooks)
        return "\n\n".join(hook["hook_content"].strip() for hook in hooks if hook["hook_content"].strip())

    compiled_prompt = HOOK_PATTERN.sub(replace_placeholder, system_prompt)
    compiled_prompt = re.sub(r"\n{3,}", "\n\n", compiled_prompt).strip()

    return {
        "raw_prompt": system_prompt,
        "compiled_prompt": compiled_prompt,
        "detected_groups": groups,
        "resolved_hooks": resolved_hooks,
        "unresolved_groups": unresolved_groups,
    }
