import json

from errors import PromptAdminError
from hook_repository import export_hooks
from repository import export_prompts, list_prompt_families
from validation import validate_import_payload


def build_download_payload(prompt_key, system_prompt, download_format):
    if download_format == "txt":
        return system_prompt, "text/plain; charset=utf-8", f"{prompt_key}.txt"
    if download_format == "md":
        lines = system_prompt.splitlines() or [""]
        if system_prompt.endswith("\n"):
            lines.append("")
        content = "# Prompt Export\n\n"
        content += f"**Prompt key:** `{prompt_key}`\n\n"
        content += "## System prompt\n\n"
        content += "\n".join(f"    {line}" for line in lines) + "\n"
        return content, "text/markdown; charset=utf-8", f"{prompt_key}.md"
    raise PromptAdminError("Download format must be txt or md.")


def export_families(include_deleted=False):
    return [
        {
            "family_key": family["family_key"],
            "description": family.get("description", ""),
        }
        for family in list_prompt_families(include_deleted=include_deleted)
    ]


def build_export_payload(include_deleted=False):
    content = json.dumps(
        {
            "families": export_families(include_deleted=include_deleted),
            "prompts": export_prompts(include_deleted=include_deleted),
            "hooks": export_hooks(include_deleted=include_deleted),
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    return content, "application/json; charset=utf-8", "prompt-admin-export.json"


def parse_import_payload(raw_json):
    try:
        payload = json.loads(raw_json or "")
    except json.JSONDecodeError as exc:
        raise PromptAdminError(f"Invalid JSON: {exc}") from exc
    return validate_import_payload(payload)
