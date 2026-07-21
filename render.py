import html
from string import Template
from urllib.parse import quote

from config import TEMPLATES_DIR
from validation import hook_group_suffix


def render_template(template_name, **context):
    template_path = TEMPLATES_DIR / template_name
    return Template(template_path.read_text(encoding="utf-8")).safe_substitute(context)


def format_datetime(value):
    if not value:
        return ""
    if hasattr(value, "strftime"):
        suffix = " UTC" if getattr(value, "tzinfo", None) else ""
        return value.strftime("%d %b %Y, %H:%M") + suffix
    return str(value).split(".")[0]


def layout(title, body):
    return render_template("layout.html", title=html.escape(title), content=body)


def render_message_page(title, message):
    body = render_template("message.html", title=html.escape(title), message=html.escape(message))
    return layout(title, body)


def render_api_docs():
    return layout("Prompt API", render_template("api_docs.html"))


def selected_attr(value, selected_value):
    return "selected" if value == selected_value else ""


def disabled_attr(value):
    return "disabled" if value else ""


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def render_category_options(categories, selected_category):
    options = [f'<option value="" {selected_attr("", selected_category)}>All categories</option>']
    for category in categories:
        escaped_category = html.escape(category)
        options.append(
            f'<option value="{escaped_category}" {selected_attr(category, selected_category)}>{escaped_category}</option>'
        )
    return "".join(options)


def render_prompt_family_options(families, selected_family_key=""):
    options = [f'<option value="" {selected_attr("", selected_family_key)}>Standalone</option>']
    for family in families or []:
        family_key = family["family_key"]
        label = family_key
        if family.get("prompt_count"):
            label += f" ({family['prompt_count']} prompts)"
        options.append(
            f'<option value="{html.escape(family_key)}" {selected_attr(family_key, selected_family_key)}>{html.escape(label)}</option>'
        )
    return "".join(options)


def render_index(summaries, categories=None, filters=None):
    categories = categories or []
    filters = filters or {"category": "", "status": "all", "q": ""}
    selected_category = filters.get("category", "")
    selected_status = filters.get("status", "all") or "all"
    query = filters.get("q", "")
    rows = []
    total_chars = 0
    total_lines = 0

    for summary in summaries:
        prompt_key = summary["prompt_key"]
        is_active = bool(summary.get("is_active"))
        total_chars += summary["char_count"]
        total_lines += summary["line_count"]
        rows.append(
            render_template(
                "index_row.html",
                prompt_key=html.escape(prompt_key),
                url_key=quote(prompt_key, safe=""),
                prompt_type=html.escape(summary.get("category") or "custom"),
                line_count=str(summary["line_count"]),
                char_count=str(summary["char_count"]),
                updated_at=html.escape(format_datetime(summary["updated_at"])),
                is_active_attr="1" if is_active else "0",
                status="Active" if is_active else "Inactive",
            )
        )

    if not rows:
        rows.append(render_template("index_empty_row.html"))

    return layout(
        "Prompt Admin",
        render_template(
            "index.html",
            rows_html="".join(rows),
            prompt_count=str(len(summaries)),
            active_count=str(sum(1 for item in summaries if item.get("is_active"))),
            total_lines=str(total_lines),
            total_chars=str(total_chars),
            category_options=render_category_options(categories, selected_category),
            status_all_selected=selected_attr("all", selected_status),
            status_active_selected=selected_attr("active", selected_status),
            status_inactive_selected=selected_attr("inactive", selected_status),
            query=html.escape(query),
        ),
    )


def render_families(families, filters=None):
    filters = filters or {"q": ""}
    query = filters.get("q", "")
    rows = []
    for family in families:
        family_key = family["family_key"]
        rows.append(
            render_template(
                "families_row.html",
                family_key=html.escape(family_key),
                url_key=quote(family_key, safe=""),
                description=html.escape(family.get("description") or ""),
                prompt_count=str(family.get("prompt_count", 0)),
                updated_at=html.escape(format_datetime(family.get("updated_at"))),
            )
        )
    if not rows:
        rows.append(render_template("families_empty_row.html"))
    return layout(
        "Prompt Families",
        render_template(
            "families.html",
            rows_html="".join(rows),
            family_count=str(len(families)),
            query=html.escape(query),
        ),
    )


def render_family_overview(family, family_items):
    family_key = family["family_key"]
    rows = []
    for item in family_items:
        prompt_key = item["prompt_key"]
        rows.append(
            render_template(
                "family_overview_row.html",
                family_item=str(item.get("family_version") or ""),
                prompt_key=html.escape(prompt_key),
                url_key=quote(prompt_key, safe=""),
                category=html.escape(item.get("category") or "custom"),
                status="Active" if item.get("is_active") else "Inactive",
                updated_at=html.escape(format_datetime(item.get("updated_at"))),
            )
        )
    if not rows:
        rows.append(render_template("family_overview_empty_row.html"))

    return layout(
        "Prompt Family",
        render_template(
            "family_overview.html",
            family_key=html.escape(family_key),
            url_key=quote(family_key, safe=""),
            description=html.escape(family.get("description") or ""),
            prompt_count=str(family.get("prompt_count", 0)),
            max_item=str(family.get("max_version", 0)),
            rows_html="".join(rows),
        ),
    )


def render_family_delete_actions(family):
    family_key = (family or {}).get("family_key", "")
    if not family_key:
        return ""
    return render_template("family_delete_actions.html", url_key=quote(family_key, safe=""))


def render_family_form(family=None, error=""):
    family = family or {}
    family_key = family.get("family_key", "")
    return layout(
        "Prompt Family",
        render_template(
            "family_form.html",
            error_html=render_template("error_card.html", error=html.escape(error)) if error else "",
            family_key=html.escape(family_key),
            readonly_attr="readonly" if family_key else "",
            description=html.escape(family.get("description", "")),
            prompt_count=str(family.get("prompt_count", 0)),
            max_version=str(family.get("max_version", 0)),
            family_delete_actions_html=render_family_delete_actions(family),
        ),
    )


def render_family_delete_confirmation(family):
    family_key = family["family_key"]
    return layout(
        "Delete Prompt Family",
        render_template(
            "family_delete_confirmation.html",
            family_key=html.escape(family_key),
            url_key=quote(family_key, safe=""),
            prompt_count=str(family.get("prompt_count", 0)),
        ),
    )


def render_family_nav_link(label, prompt):
    if not prompt:
        return f'<span class="button secondary disabled-button">{html.escape(label)}</span>'
    return f'<a class="button secondary" href="/edit?key={quote(prompt["prompt_key"], safe="")}">{html.escape(label)}</a>'


def render_family_version_options(family_versions, current_prompt_key, pending_prompt=None):
    options = []
    for version in family_versions:
        prompt_key = version["prompt_key"]
        item_number = version.get("family_version")
        label = f"#{item_number} — {prompt_key}"
        if not version.get("is_active"):
            label += " (inactive)"
        options.append(
            f'<option value="{html.escape(prompt_key)}" {selected_attr(prompt_key, current_prompt_key)}>{html.escape(label)}</option>'
        )

    if pending_prompt and pending_prompt.get("prompt_key") not in {item["prompt_key"] for item in family_versions}:
        prompt_key = pending_prompt["prompt_key"]
        item_number = pending_prompt.get("family_version")
        label = f"#{item_number} — {prompt_key} (not saved yet)"
        options.append(
            f'<option value="{html.escape(prompt_key)}" selected disabled>{html.escape(label)}</option>'
        )

    return "".join(options)


def render_prompt_family_actions(prompt, family_versions=None):
    prompt = prompt or {}
    prompt_key = prompt.get("prompt_key", "")
    if not prompt_key:
        return ""

    family_key = prompt.get("prompt_family_key") or ""
    family_version = prompt.get("family_version") or ""
    if not family_key:
        return """
        <details class="action-card">
          <summary>Prompt family</summary>
          <div class="prompt-family-card">
            <p class="help-text">This prompt is standalone. Select a family in the form to attach it without changing its prompt key, or use <strong>Clone as new family item</strong> to create another grouped prompt.</p>
            <a class="button secondary" href="/families">Manage families</a>
          </div>
        </details>
        """

    family_versions = family_versions or []
    current_version = safe_int(family_version)
    previous_prompt = None
    next_prompt = None
    for version in family_versions:
        version_number = safe_int(version.get("family_version"))
        if current_version and version_number and version_number < current_version:
            previous_prompt = version
        if current_version and version_number and version_number > current_version and not next_prompt:
            next_prompt = version

    version_options = render_family_version_options(family_versions, prompt_key, prompt)
    version_switcher = ""
    if version_options:
        version_switcher = f"""
        <form method="get" action="/edit" class="family-switcher">
          <select name="key" aria-label="Prompt family item">
            {version_options}
          </select>
          <button type="submit" class="secondary">Open</button>
        </form>
        """

    family_item_label = f"#{family_version}" if current_version else "unknown"
    return f"""
    <details class="action-card" open>
      <summary>Prompt family</summary>
      <div class="prompt-family-card">
        <dl class="compact-meta-list">
          <div>
            <dt>Family</dt>
            <dd><code>{html.escape(family_key)}</code></dd>
          </div>
          <div>
            <dt>Family item</dt>
            <dd>{html.escape(family_item_label)}</dd>
          </div>
        </dl>
        {version_switcher}
        <div class="family-nav-actions">
          {render_family_nav_link('← Previous', previous_prompt)}
          {render_family_nav_link('Next →', next_prompt)}
        </div>
        <a class="button secondary" href="/family?key={quote(family_key, safe='')}">Open family</a>
      </div>
    </details>
    """


def render_form(prompt=None, error="", validation_warnings=None, family_versions=None, families=None):
    prompt = prompt or {}
    prompt_key = prompt.get("prompt_key", "")
    system_prompt = prompt.get("system_prompt", "")
    is_active = prompt.get("is_active", True)
    is_clone = prompt.get("_is_clone", False)
    prompt_family_key = prompt.get("prompt_family_key") or ""
    selected_prompt_family_key = prompt.get("selected_prompt_family_key", prompt_family_key) or ""
    family_version = prompt.get("family_version") or ""
    clone_source_key = prompt.get("_clone_source_key") or prompt.get("clone_source_key") or ""
    is_generated_version = bool(prompt_family_key and family_version)
    validation_warnings = validation_warnings or []

    warning_items = "".join(f"<li>{html.escape(item)}</li>" for item in validation_warnings)
    validation_html = render_template("validation_result.html", warning_items=warning_items) if warning_items else ""
    family_select_disabled = bool(is_clone)

    return layout(
        "Edit Prompt",
        render_template(
            "form.html",
            error_html=render_template("error_card.html", error=html.escape(error)) if error else "",
            validation_html=validation_html,
            prompt_key=html.escape(prompt_key),
            readonly_attr="readonly" if prompt_key and (not is_clone or is_generated_version) else "",
            prompt_family_key=html.escape(prompt_family_key),
            family_version=html.escape(str(family_version)),
            selected_prompt_family_key=html.escape(selected_prompt_family_key),
            family_options_html=render_prompt_family_options(families or [], selected_prompt_family_key),
            family_select_disabled_attr=disabled_attr(family_select_disabled),
            family_hidden_input_html=(
                f'<input type="hidden" name="selected_prompt_family_key" value="{html.escape(selected_prompt_family_key)}">'
                if family_select_disabled else ""
            ),
            clone_source_key=html.escape(clone_source_key),
            system_prompt=html.escape(system_prompt),
            category=html.escape(prompt.get("category", "")),
            checked_attr="checked" if is_active else "",
            line_count=str(len(system_prompt.splitlines()) if system_prompt else 0),
            char_count=str(len(system_prompt)),
            family_actions_html=render_prompt_family_actions(prompt, family_versions),
            download_actions_html=render_template(
                "download_actions.html",
                prompt_key=html.escape(prompt_key),
                url_key=quote(prompt_key, safe=""),
            ) if prompt_key and not is_clone else "",
        ),
    )


def render_delete_confirmation(prompt_key):
    return layout(
        "Delete Prompt",
        render_template(
            "delete_confirmation.html",
            prompt_key=html.escape(prompt_key),
            url_key=quote(prompt_key, safe=""),
        ),
    )


def render_deleted(summaries, hook_summaries=None, family_summaries=None):
    rows = []
    for summary in summaries:
        if not summary.get("deleted_at"):
            continue
        prompt_key = summary["prompt_key"]
        rows.append(
            render_template(
                "deleted_row.html",
                item_type="Prompt",
                item_key=html.escape(prompt_key),
                restore_action="/restore",
                purge_action="/purge",
                deleted_at=html.escape(format_datetime(summary["deleted_at"])),
            )
        )
    for summary in family_summaries or []:
        if not summary.get("deleted_at"):
            continue
        family_key = summary["family_key"]
        rows.append(
            render_template(
                "deleted_row.html",
                item_type="Family",
                item_key=html.escape(family_key),
                restore_action="/family-restore",
                purge_action="/family-purge",
                deleted_at=html.escape(format_datetime(summary["deleted_at"])),
            )
        )
    for summary in hook_summaries or []:
        if not summary.get("deleted_at"):
            continue
        hook_key = summary["hook_key"]
        rows.append(
            render_template(
                "deleted_row.html",
                item_type="Hook",
                item_key=html.escape(hook_key),
                restore_action="/hook-restore",
                purge_action="/hook-purge",
                deleted_at=html.escape(format_datetime(summary["deleted_at"])),
            )
        )
    if not rows:
        rows.append(render_template("deleted_empty_row.html"))
    return layout("Deleted Records", render_template("deleted.html", rows_html="".join(rows)))


def render_history(prompt_key, versions):
    rows = []
    for version in versions:
        rows.append(
            render_template(
                "history_row.html",
                version_id=str(version["id"]),
                created_at=html.escape(format_datetime(version["created_at"])),
                char_count=str(len(version["system_prompt"] or "")),
            )
        )
    if not rows:
        rows.append(render_template("history_empty_row.html"))
    return layout(
        "Prompt History",
        render_template(
            "history.html",
            prompt_key=html.escape(prompt_key),
            url_key=quote(prompt_key, safe=""),
            rows_html="".join(rows),
        ),
    )


def render_hooks(hooks):
    rows = []
    for hook in hooks:
        hook_key = hook["hook_key"]
        rows.append(
            render_template(
                "hooks_row.html",
                hook_key=html.escape(hook_key),
                url_key=quote(hook_key, safe=""),
                hook_group=html.escape(hook["hook_group"]),
                category=html.escape(hook.get("category") or "custom"),
                priority=str(hook["priority"]),
                status="Active" if hook.get("is_active") else "Inactive",
                updated_at=html.escape(format_datetime(hook["updated_at"])),
            )
        )
    if not rows:
        rows.append(render_template("hooks_empty_row.html"))
    return layout("Prompt Hooks", render_template("hooks.html", rows_html="".join(rows), hook_count=str(len(hooks))))


def render_hook_form(hook=None, error="", validation_warnings=None):
    hook = hook or {"priority": 100, "is_active": True}
    hook_key = hook.get("hook_key", "")
    hook_content = hook.get("hook_content", "")
    is_clone = hook.get("_is_clone", False)
    warning_items = "".join(f"<li>{html.escape(item)}</li>" for item in validation_warnings or [])
    validation_html = render_template("validation_result.html", warning_items=warning_items) if warning_items else ""
    return layout(
        "Edit Hook",
        render_template(
            "hook_form.html",
            error_html=render_template("error_card.html", error=html.escape(error)) if error else "",
            validation_html=validation_html,
            hook_key=html.escape(hook_key),
            readonly_attr="readonly" if hook_key and not is_clone else "",
            hook_group=html.escape(hook_group_suffix(hook.get("hook_group", ""))),
            hook_content=html.escape(hook_content),
            description=html.escape(hook.get("description", "")),
            category=html.escape(hook.get("category", "")),
            priority=str(hook.get("priority", 100)),
            checked_attr="checked" if hook.get("is_active", True) else "",
            line_count=str(len(hook_content.splitlines()) if hook_content else 0),
            char_count=str(len(hook_content)),
            url_key=quote(hook_key, safe=""),
            hook_actions_html=render_template("hook_actions.html", url_key=quote(hook_key, safe="")) if hook_key and not is_clone else "",
        ),
    )


def render_hook_delete_confirmation(hook_key):
    return layout(
        "Delete Hook",
        render_template(
            "hook_delete_confirmation.html",
            hook_key=html.escape(hook_key),
            url_key=quote(hook_key, safe=""),
        ),
    )


def render_hook_history(hook_key, versions):
    rows = []
    for version in versions:
        rows.append(
            render_template(
                "history_row.html",
                version_id=str(version["id"]),
                created_at=html.escape(format_datetime(version["created_at"])),
                char_count=str(len(version["hook_content"] or "")),
            )
        )
    if not rows:
        rows.append(render_template("history_empty_row.html"))
    return layout(
        "Hook History",
        render_template(
            "hook_history.html",
            hook_key=html.escape(hook_key),
            url_key=quote(hook_key, safe=""),
            rows_html="".join(rows),
        ),
    )


def render_prompt_preview(prompt_key, compiled):
    group_items = "".join(f"<li><code>#{html.escape(group)}</code></li>" for group in compiled["detected_groups"])
    hook_items = "".join(
        f"<li><code>{html.escape(hook['hook_key'])}</code> — {html.escape(hook['hook_group'])}</li>"
        for hook in compiled["resolved_hooks"]
    )
    unresolved_items = "".join(f"<li><code>#{html.escape(group)}</code></li>" for group in compiled["unresolved_groups"])
    return layout(
        "Compiled Prompt Preview",
        render_template(
            "prompt_preview.html",
            prompt_key=html.escape(prompt_key),
            url_key=quote(prompt_key, safe=""),
            raw_prompt=html.escape(compiled["raw_prompt"]),
            compiled_prompt=html.escape(compiled["compiled_prompt"]),
            group_items=group_items or "<li>none</li>",
            hook_items=hook_items or "<li>none</li>",
            unresolved_items=unresolved_items or "<li>none</li>",
        ),
    )


def render_import_page(error="", result_html=""):
    return layout(
        "Import Prompts",
        render_template(
            "import.html",
            error_html=render_template("error_card.html", error=html.escape(error)) if error else "",
            result_html=result_html,
        ),
    )


def render_import_result(plan, dry_run):
    family_plan = plan.get("families", {"create": [], "update": []})
    prompt_plan = plan["prompts"]
    hook_plan = plan["hooks"]
    return render_template(
        "import_result.html",
        mode="Preview" if dry_run else "Imported",
        family_create_count=str(len(family_plan["create"])),
        family_update_count=str(len(family_plan["update"])),
        family_create_items=html.escape(", ".join(family_plan["create"]) or "none"),
        family_update_items=html.escape(", ".join(family_plan["update"]) or "none"),
        prompt_create_count=str(len(prompt_plan["create"])),
        prompt_update_count=str(len(prompt_plan["update"])),
        prompt_create_items=html.escape(", ".join(prompt_plan["create"]) or "none"),
        prompt_update_items=html.escape(", ".join(prompt_plan["update"]) or "none"),
        hook_create_count=str(len(hook_plan["create"])),
        hook_update_count=str(len(hook_plan["update"])),
        hook_create_items=html.escape(", ".join(hook_plan["create"]) or "none"),
        hook_update_items=html.escape(", ".join(hook_plan["update"]) or "none"),
    )
