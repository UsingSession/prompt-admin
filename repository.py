from db import connect
from errors import PromptAdminError
from validation import validate_key


VERSION_KEY_SEPARATOR = "_v"


def normalize_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def normalize_optional_key(value):
    value = (value or "").strip()
    if not value:
        return None
    return validate_key(value)


def normalize_optional_version(value):
    if value is None or value == "":
        return None
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise PromptAdminError("Family item number must be a number.") from exc
    if version < 1:
        raise PromptAdminError("Family item number must be greater than zero.")
    return version


def delete_keyword():
    return "".join(chr(code) for code in [68, 69, 76, 69, 84, 69])


def versioned_prompt_key(family_key, family_version):
    family_key = validate_key(family_key)
    suffix = f"{VERSION_KEY_SEPARATOR}{family_version}"
    if len(family_key) + len(suffix) > 120:
        raise PromptAdminError(
            "Family key is too long to generate a versioned prompt key. Shorten the family key to leave room for the _vN suffix."
        )
    return validate_key(f"{family_key}{suffix}")


def prompt_summary_from_row(row):
    return {
        "prompt_key": row[0],
        "category": row[1] or "",
        "prompt_family_key": row[2],
        "family_version": row[3],
        "is_active": row[4],
        "updated_at": row[5],
        "deleted_at": row[6],
        "char_count": row[7],
        "line_count": row[8],
    }


def prompt_from_row(row):
    return {
        "prompt_key": row[0],
        "system_prompt": row[1],
        "category": row[2] or "",
        "prompt_family_key": row[3],
        "family_version": row[4],
        "is_active": row[5],
        "updated_at": row[6],
        "deleted_at": row[7],
    }


def family_version_from_row(row):
    return {
        "prompt_key": row[0],
        "prompt_family_key": row[1],
        "family_version": row[2],
        "category": row[3] or "",
        "is_active": row[4],
        "updated_at": row[5],
        "deleted_at": row[6],
    }


def prompt_family_from_row(row):
    return {
        "family_key": row[0],
        "description": row[1] or "",
        "prompt_count": row[2] or 0,
        "max_version": row[3] or 0,
        "updated_at": row[4],
        "deleted_at": row[5],
    }


def build_prompt_summary_query(where_parts):
    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    return f"""
        SELECT
            prompt_key,
            category,
            prompt_family_key,
            family_version,
            is_active,
            updated_at,
            deleted_at,
            char_length(system_prompt) AS char_count,
            CASE
                WHEN system_prompt = '' THEN 0
                ELSE array_length(
                    regexp_split_to_array(
                        regexp_replace(system_prompt, E'[\r\n]+$', ''),
                        E'\r\n|\r|\n'
                    ),
                    1
                )
            END AS line_count
        FROM ai_system_prompts
        {where_clause}
        ORDER BY prompt_key ASC;
    """


def prompt_select_columns():
    return """
        prompt_key,
        system_prompt,
        category,
        prompt_family_key,
        family_version,
        is_active,
        updated_at,
        deleted_at
    """


def list_prompt_summaries(include_deleted=False):
    where_parts = [] if include_deleted else ["deleted_at IS NULL"]
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(build_prompt_summary_query(where_parts))
            return [prompt_summary_from_row(row) for row in cursor.fetchall()]


def list_filtered_prompt_summaries(category="", status="all", query=""):
    where_parts = ["deleted_at IS NULL"]
    values = []

    category = (category or "").strip()
    if category:
        where_parts.append("category = %s")
        values.append(category)

    status = (status or "all").strip().lower()
    if status == "active":
        where_parts.append("is_active = TRUE")
    elif status == "inactive":
        where_parts.append("is_active = FALSE")

    query = (query or "").strip()
    if query:
        where_parts.append("(prompt_key ILIKE %s OR category ILIKE %s OR prompt_family_key ILIKE %s)")
        search_value = f"%{query}%"
        values.extend([search_value, search_value, search_value])

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(build_prompt_summary_query(where_parts), values)
            return [prompt_summary_from_row(row) for row in cursor.fetchall()]


def list_prompt_categories():
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT category
                FROM ai_system_prompts
                WHERE deleted_at IS NULL
                  AND category <> ''
                ORDER BY category ASC;
                """
            )
            return [row[0] for row in cursor.fetchall()]


def get_prompt(prompt_key, include_deleted=False):
    prompt_key = validate_key(prompt_key)
    deleted_filter = "" if include_deleted else "AND deleted_at IS NULL"
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {prompt_select_columns()}
                FROM ai_system_prompts
                WHERE prompt_key = %s {deleted_filter};
                """,
                (prompt_key,),
            )
            row = cursor.fetchone()
            return prompt_from_row(row) if row else None


def unique_prompt_keys(prompt_keys):
    clean_keys = []
    seen = set()
    for prompt_key in prompt_keys or []:
        clean_key = validate_key(prompt_key)
        if clean_key in seen:
            continue
        seen.add(clean_key)
        clean_keys.append(clean_key)
    return clean_keys


def list_active_prompts(category="", prompt_keys=None):
    where_parts = ["deleted_at IS NULL", "is_active = TRUE"]
    values = []

    category = (category or "").strip()
    if category:
        where_parts.append("category = %s")
        values.append(category)

    requested_keys = unique_prompt_keys(prompt_keys)
    if requested_keys:
        placeholders = ", ".join(["%s"] * len(requested_keys))
        where_parts.append(f"prompt_key IN ({placeholders})")
        values.extend(requested_keys)

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {prompt_select_columns()}
                FROM ai_system_prompts
                WHERE {' AND '.join(where_parts)}
                ORDER BY prompt_key ASC;
                """,
                values,
            )
            prompts = [prompt_from_row(row) for row in cursor.fetchall()]

    if not requested_keys:
        return prompts

    prompts_by_key = {prompt["prompt_key"]: prompt for prompt in prompts}
    ordered_prompts = []
    for prompt_key in requested_keys:
        prompt = prompts_by_key.get(prompt_key)
        if prompt:
            ordered_prompts.append(prompt)
    return ordered_prompts


def list_prompt_families(include_deleted=False):
    deleted_filter = "" if include_deleted else "WHERE f.deleted_at IS NULL"
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    f.family_key,
                    f.description,
                    COUNT(p.prompt_key) FILTER (WHERE p.deleted_at IS NULL) AS prompt_count,
                    COALESCE(MAX(p.family_version), 0) AS max_version,
                    f.updated_at,
                    f.deleted_at
                FROM ai_prompt_families f
                LEFT JOIN ai_system_prompts p ON p.prompt_family_key = f.family_key
                {deleted_filter}
                GROUP BY f.family_key, f.description, f.updated_at, f.deleted_at
                ORDER BY f.family_key ASC;
                """
            )
            return [prompt_family_from_row(row) for row in cursor.fetchall()]


def get_prompt_family(family_key, include_deleted=False):
    family_key = validate_key(family_key)
    deleted_filter = "" if include_deleted else "AND f.deleted_at IS NULL"
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    f.family_key,
                    f.description,
                    COUNT(p.prompt_key) FILTER (WHERE p.deleted_at IS NULL) AS prompt_count,
                    COALESCE(MAX(p.family_version), 0) AS max_version,
                    f.updated_at,
                    f.deleted_at
                FROM ai_prompt_families f
                LEFT JOIN ai_system_prompts p ON p.prompt_family_key = f.family_key
                WHERE f.family_key = %s {deleted_filter}
                GROUP BY f.family_key, f.description, f.updated_at, f.deleted_at;
                """,
                (family_key,),
            )
            row = cursor.fetchone()
            return prompt_family_from_row(row) if row else None


def save_prompt_family(family_key, description=""):
    family_key = validate_key(family_key)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ai_prompt_families (family_key, description, updated_at, deleted_at)
                VALUES (%s, %s, NOW(), NULL)
                ON CONFLICT (family_key)
                DO UPDATE SET
                    description = EXCLUDED.description,
                    updated_at = NOW(),
                    deleted_at = NULL;
                """,
                (family_key, description.strip()),
            )
        connection.commit()


def ensure_prompt_family(cursor, family_key, description=""):
    family_key = validate_key(family_key)
    cursor.execute(
        """
        INSERT INTO ai_prompt_families (family_key, description, updated_at, deleted_at)
        VALUES (%s, %s, NOW(), NULL)
        ON CONFLICT (family_key)
        DO UPDATE SET
            description = CASE
                WHEN EXCLUDED.description <> '' THEN EXCLUDED.description
                ELSE ai_prompt_families.description
            END,
            updated_at = NOW(),
            deleted_at = NULL;
        """,
        (family_key, description.strip()),
    )


def prompt_family_prompt_count(cursor, family_key, include_deleted=False):
    deleted_filter = "" if include_deleted else "AND deleted_at IS NULL"
    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM ai_system_prompts
        WHERE prompt_family_key = %s {deleted_filter};
        """,
        (family_key,),
    )
    return cursor.fetchone()[0] or 0


def soft_delete_prompt_family(family_key):
    family_key = validate_key(family_key)
    with connect() as connection:
        with connection.cursor() as cursor:
            if prompt_family_prompt_count(cursor, family_key):
                raise PromptAdminError("Cannot delete a family while prompts are attached. Detach or delete those prompts first.")
            cursor.execute(
                "UPDATE ai_prompt_families SET deleted_at = NOW() WHERE family_key = %s;",
                (family_key,),
            )
        connection.commit()


def restore_prompt_family(family_key):
    family_key = validate_key(family_key)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE ai_prompt_families SET deleted_at = NULL WHERE family_key = %s;",
                (family_key,),
            )
        connection.commit()


def permanently_delete_prompt_family(family_key):
    family_key = validate_key(family_key)
    with connect() as connection:
        with connection.cursor() as cursor:
            if prompt_family_prompt_count(cursor, family_key, include_deleted=True):
                raise PromptAdminError("Cannot permanently delete a family while any prompts still reference it.")
            cursor.execute(
                f"{delete_keyword()} FROM ai_prompt_families WHERE family_key = %s AND deleted_at IS NOT NULL;",
                (family_key,),
            )
        connection.commit()


def prompt_key_exists(cursor, prompt_key):
    cursor.execute(
        "SELECT 1 FROM ai_system_prompts WHERE prompt_key = %s;",
        (prompt_key,),
    )
    return bool(cursor.fetchone())


def family_version_exists(cursor, family_key, family_version):
    cursor.execute(
        """
        SELECT 1
        FROM ai_system_prompts
        WHERE prompt_family_key = %s
          AND family_version = %s;
        """,
        (family_key, family_version),
    )
    return bool(cursor.fetchone())


def next_family_version(cursor, family_key, minimum_version=1):
    family_key = validate_key(family_key)
    cursor.execute(
        """
        SELECT COALESCE(MAX(family_version), 0)
        FROM ai_system_prompts
        WHERE prompt_family_key = %s;
        """,
        (family_key,),
    )
    version = max((cursor.fetchone()[0] or 0) + 1, minimum_version)
    while family_version_exists(cursor, family_key, version):
        version += 1
    return version


def next_family_version_and_key(cursor, family_key, minimum_version=1):
    family_key = validate_key(family_key)
    version = next_family_version(cursor, family_key, minimum_version)
    while True:
        prompt_key = versioned_prompt_key(family_key, version)
        if not prompt_key_exists(cursor, prompt_key):
            return version, prompt_key
        version += 1


def assign_source_prompt_to_family(cursor, source_prompt_key, family_key):
    source_prompt_key = normalize_optional_key(source_prompt_key)
    if not source_prompt_key:
        return

    cursor.execute(
        """
        SELECT prompt_family_key, family_version
        FROM ai_system_prompts
        WHERE prompt_key = %s;
        """,
        (source_prompt_key,),
    )
    source = cursor.fetchone()
    if not source:
        return

    source_family_key, source_family_version = source
    if source_family_key:
        if source_family_key != family_key:
            raise PromptAdminError("Source prompt belongs to another family.")
        return

    if family_version_exists(cursor, family_key, 1):
        raise PromptAdminError("Cannot assign source prompt as first family item because this family already has item #1.")
    cursor.execute(
        """
        UPDATE ai_system_prompts
        SET prompt_family_key = %s,
            family_version = 1,
            updated_at = NOW()
        WHERE prompt_key = %s
          AND prompt_family_key IS NULL;
        """,
        (family_key, source_prompt_key),
    )


def resolve_prompt_family_assignment(
    cursor,
    current,
    prompt_family_key,
    family_version,
    selected_prompt_family_key,
    clone_source_key,
):
    if selected_prompt_family_key is None or clone_source_key:
        return prompt_family_key, family_version

    selected_prompt_family_key = normalize_optional_key(selected_prompt_family_key)
    if not selected_prompt_family_key:
        return None, None

    current_family_key = current[3] if current else None
    current_family_version = current[4] if current else None
    if current_family_key == selected_prompt_family_key and current_family_version:
        return current_family_key, current_family_version

    ensure_prompt_family(cursor, selected_prompt_family_key)
    return selected_prompt_family_key, next_family_version(cursor, selected_prompt_family_key)


def save_prompt(
    prompt_key,
    system_prompt,
    category="",
    is_active=True,
    prompt_family_key="",
    family_version="",
    clone_source_key="",
    selected_prompt_family_key=None,
):
    prompt_key = validate_key(prompt_key)
    is_active = normalize_bool(is_active)
    prompt_family_key = normalize_optional_key(prompt_family_key)
    family_version = normalize_optional_version(family_version)

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT system_prompt, category, is_active, prompt_family_key, family_version
                FROM ai_system_prompts
                WHERE prompt_key = %s;
                """,
                (prompt_key,),
            )
            current = cursor.fetchone()

            prompt_family_key, family_version = resolve_prompt_family_assignment(
                cursor,
                current,
                prompt_family_key,
                family_version,
                selected_prompt_family_key,
                clone_source_key,
            )

            if bool(prompt_family_key) != bool(family_version):
                raise PromptAdminError("Prompt family and item number must be set together.")

            if prompt_family_key:
                ensure_prompt_family(cursor, prompt_family_key)
                assign_source_prompt_to_family(cursor, clone_source_key, prompt_family_key)

            if current:
                cursor.execute(
                    """
                    INSERT INTO ai_system_prompt_versions
                        (prompt_key, system_prompt, category, is_active)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (prompt_key, current[0], current[1] or "", current[2]),
                )

            cursor.execute(
                """
                INSERT INTO ai_system_prompts
                    (
                        prompt_key,
                        system_prompt,
                        category,
                        prompt_family_key,
                        family_version,
                        is_active,
                        updated_at,
                        deleted_at
                    )
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NULL)
                ON CONFLICT (prompt_key)
                DO UPDATE SET
                    system_prompt = EXCLUDED.system_prompt,
                    category = EXCLUDED.category,
                    prompt_family_key = EXCLUDED.prompt_family_key,
                    family_version = EXCLUDED.family_version,
                    is_active = EXCLUDED.is_active,
                    updated_at = NOW(),
                    deleted_at = NULL;
                """,
                (prompt_key, system_prompt, category.strip(), prompt_family_key, family_version, is_active),
            )
        connection.commit()


def build_prompt_clone(prompt_key):
    source_prompt = get_prompt(prompt_key)
    if not source_prompt:
        return None

    with connect() as connection:
        with connection.cursor() as cursor:
            if source_prompt.get("prompt_family_key"):
                family_key = source_prompt["prompt_family_key"]
                minimum_version = 1
            else:
                family_key = source_prompt["prompt_key"]
                minimum_version = 2
            family_version, new_prompt_key = next_family_version_and_key(cursor, family_key, minimum_version)

    cloned_prompt = dict(source_prompt)
    cloned_prompt["prompt_key"] = new_prompt_key
    cloned_prompt["prompt_family_key"] = family_key
    cloned_prompt["family_version"] = family_version
    cloned_prompt["_is_clone"] = True
    cloned_prompt["_clone_source_key"] = source_prompt["prompt_key"]
    return cloned_prompt


def list_prompt_family_versions(family_key):
    family_key = normalize_optional_key(family_key)
    if not family_key:
        return []

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    prompt_key,
                    prompt_family_key,
                    family_version,
                    category,
                    is_active,
                    updated_at,
                    deleted_at
                FROM ai_system_prompts
                WHERE prompt_family_key = %s
                  AND deleted_at IS NULL
                ORDER BY family_version ASC, prompt_key ASC;
                """,
                (family_key,),
            )
            return [family_version_from_row(row) for row in cursor.fetchall()]


def soft_delete_prompt(prompt_key):
    prompt_key = validate_key(prompt_key)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE ai_system_prompts SET deleted_at = NOW() WHERE prompt_key = %s;",
                (prompt_key,),
            )
        connection.commit()


def restore_prompt(prompt_key):
    prompt_key = validate_key(prompt_key)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE ai_system_prompts SET deleted_at = NULL WHERE prompt_key = %s;",
                (prompt_key,),
            )
        connection.commit()


def permanently_delete_prompt(prompt_key):
    prompt_key = validate_key(prompt_key)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                {delete_keyword()} FROM ai_system_prompt_versions v
                WHERE v.prompt_key = %s
                  AND EXISTS (
                      SELECT 1
                      FROM ai_system_prompts p
                      WHERE p.prompt_key = %s
                        AND p.deleted_at IS NOT NULL
                  );
                """,
                (prompt_key, prompt_key),
            )
            cursor.execute(
                f"{delete_keyword()} FROM ai_system_prompts WHERE prompt_key = %s AND deleted_at IS NOT NULL;",
                (prompt_key,),
            )
        connection.commit()


def list_prompt_versions(prompt_key):
    prompt_key = validate_key(prompt_key)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, system_prompt, category, is_active, created_at
                FROM ai_system_prompt_versions
                WHERE prompt_key = %s
                ORDER BY created_at DESC, id DESC;
                """,
                (prompt_key,),
            )
            return [
                {
                    "id": row[0],
                    "system_prompt": row[1],
                    "category": row[2] or "",
                    "is_active": row[3],
                    "created_at": row[4],
                }
                for row in cursor.fetchall()
            ]


def export_prompts(include_deleted=False):
    where_clause = "" if include_deleted else "WHERE deleted_at IS NULL"
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {prompt_select_columns()}
                FROM ai_system_prompts
                {where_clause}
                ORDER BY prompt_key ASC;
                """
            )
            return [prompt_from_row(row) for row in cursor.fetchall()]


def import_prompts(prompts, dry_run=True):
    plan = {"create": [], "update": []}
    for prompt in prompts:
        prompt_key = validate_key(prompt.get("prompt_key"))
        existing = get_prompt(prompt_key, include_deleted=True)
        target = plan["update"] if existing else plan["create"]
        target.append(prompt_key)

        if not dry_run:
            family_key = prompt.get("prompt_family_key")
            family_version = prompt.get("family_version")
            if existing and "prompt_family_key" not in prompt and "family_version" not in prompt:
                family_key = existing.get("prompt_family_key")
                family_version = existing.get("family_version")
            save_prompt(
                prompt_key,
                prompt.get("system_prompt", ""),
                prompt.get("category", ""),
                normalize_bool(prompt.get("is_active", True)),
                family_key,
                family_version,
            )

    return plan
