from db import connect
from repository import normalize_bool
from validation import normalize_hook_group, validate_key


def validate_group(value):
    return normalize_hook_group(value)


def normalize_priority(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 100


def list_hooks(include_deleted=False):
    where_clause = "" if include_deleted else "WHERE deleted_at IS NULL"
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    hook_key,
                    hook_group,
                    description,
                    category,
                    priority,
                    is_active,
                    updated_at,
                    deleted_at,
                    char_length(hook_content) AS char_count,
                    CASE
                        WHEN hook_content = '' THEN 0
                        ELSE array_length(
                            regexp_split_to_array(
                                regexp_replace(hook_content, E'[\r\n]+$', ''),
                                E'\r\n|\r|\n'
                            ),
                            1
                        )
                    END AS line_count
                FROM ai_prompt_hooks
                {where_clause}
                ORDER BY hook_group ASC, priority ASC, hook_key ASC;
                """
            )
            return [
                {
                    "hook_key": hook_key,
                    "hook_group": hook_group,
                    "description": description or "",
                    "category": category or "",
                    "priority": priority,
                    "is_active": is_active,
                    "updated_at": updated_at,
                    "deleted_at": deleted_at,
                    "char_count": char_count,
                    "line_count": line_count,
                }
                for hook_key, hook_group, description, category, priority, is_active, updated_at, deleted_at, char_count, line_count in cursor.fetchall()
            ]


def get_hook(hook_key, include_deleted=False):
    hook_key = validate_key(hook_key)
    deleted_filter = "" if include_deleted else "AND deleted_at IS NULL"
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT hook_key, hook_group, hook_content, description, category,
                       priority, is_active, updated_at, deleted_at
                FROM ai_prompt_hooks
                WHERE hook_key = %s {deleted_filter};
                """,
                (hook_key,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "hook_key": row[0],
                "hook_group": row[1],
                "hook_content": row[2],
                "description": row[3] or "",
                "category": row[4] or "",
                "priority": row[5],
                "is_active": row[6],
                "updated_at": row[7],
                "deleted_at": row[8],
            }


def list_active_hooks_by_group(hook_group):
    hook_group = validate_group(hook_group)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT hook_key, hook_group, hook_content, description, category,
                       priority, is_active, updated_at, deleted_at
                FROM ai_prompt_hooks
                WHERE hook_group = %s
                  AND is_active = TRUE
                  AND deleted_at IS NULL
                ORDER BY priority ASC, hook_key ASC;
                """,
                (hook_group,),
            )
            return [
                {
                    "hook_key": row[0],
                    "hook_group": row[1],
                    "hook_content": row[2],
                    "description": row[3] or "",
                    "category": row[4] or "",
                    "priority": row[5],
                    "is_active": row[6],
                    "updated_at": row[7],
                    "deleted_at": row[8],
                }
                for row in cursor.fetchall()
            ]


def save_hook(hook_key, hook_group, hook_content, description="", category="", priority=100, is_active=True):
    hook_key = validate_key(hook_key)
    hook_group = validate_group(hook_group)
    priority = normalize_priority(priority)
    is_active = normalize_bool(is_active)

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT hook_group, hook_content, description, category, priority, is_active
                FROM ai_prompt_hooks
                WHERE hook_key = %s;
                """,
                (hook_key,),
            )
            current = cursor.fetchone()
            if current:
                cursor.execute(
                    """
                    INSERT INTO ai_prompt_hook_versions
                        (hook_key, hook_group, hook_content, description, category, priority, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (hook_key, current[0], current[1], current[2] or "", current[3] or "", current[4], current[5]),
                )

            cursor.execute(
                """
                INSERT INTO ai_prompt_hooks
                    (hook_key, hook_group, hook_content, description, category, priority, is_active, updated_at, deleted_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NULL)
                ON CONFLICT (hook_key)
                DO UPDATE SET
                    hook_group = EXCLUDED.hook_group,
                    hook_content = EXCLUDED.hook_content,
                    description = EXCLUDED.description,
                    category = EXCLUDED.category,
                    priority = EXCLUDED.priority,
                    is_active = EXCLUDED.is_active,
                    updated_at = NOW(),
                    deleted_at = NULL;
                """,
                (hook_key, hook_group, hook_content, description.strip(), category.strip(), priority, is_active),
            )
        connection.commit()


def soft_delete_hook(hook_key):
    hook_key = validate_key(hook_key)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE ai_prompt_hooks SET deleted_at = NOW() WHERE hook_key = %s;",
                (hook_key,),
            )
        connection.commit()


def restore_hook(hook_key):
    hook_key = validate_key(hook_key)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE ai_prompt_hooks SET deleted_at = NULL WHERE hook_key = %s;",
                (hook_key,),
            )
        connection.commit()


def permanently_delete_hook(hook_key):
    hook_key = validate_key(hook_key)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM ai_prompt_hook_versions v
                WHERE v.hook_key = %s
                  AND EXISTS (
                      SELECT 1
                      FROM ai_prompt_hooks h
                      WHERE h.hook_key = %s
                        AND h.deleted_at IS NOT NULL
                  );
                """,
                (hook_key, hook_key),
            )
            cursor.execute(
                "DELETE FROM ai_prompt_hooks WHERE hook_key = %s AND deleted_at IS NOT NULL;",
                (hook_key,),
            )
        connection.commit()


def list_hook_versions(hook_key):
    hook_key = validate_key(hook_key)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, hook_group, hook_content, description, category, priority, is_active, created_at
                FROM ai_prompt_hook_versions
                WHERE hook_key = %s
                ORDER BY created_at DESC, id DESC;
                """,
                (hook_key,),
            )
            return [
                {
                    "id": row[0],
                    "hook_group": row[1],
                    "hook_content": row[2],
                    "description": row[3] or "",
                    "category": row[4] or "",
                    "priority": row[5],
                    "is_active": row[6],
                    "created_at": row[7],
                }
                for row in cursor.fetchall()
            ]


def export_hooks(include_deleted=False):
    where_clause = "" if include_deleted else "WHERE deleted_at IS NULL"
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT hook_key, hook_group, hook_content, description, category,
                       priority, is_active, updated_at, deleted_at
                FROM ai_prompt_hooks
                {where_clause}
                ORDER BY hook_group ASC, priority ASC, hook_key ASC;
                """
            )
            return [
                {
                    "hook_key": row[0],
                    "hook_group": row[1],
                    "hook_content": row[2],
                    "description": row[3] or "",
                    "category": row[4] or "",
                    "priority": row[5],
                    "is_active": row[6],
                    "updated_at": row[7],
                    "deleted_at": row[8],
                }
                for row in cursor.fetchall()
            ]


def import_hooks(hooks, dry_run=True):
    plan = {"create": [], "update": []}
    for hook in hooks:
        hook_key = validate_key(hook.get("hook_key"))
        existing = get_hook(hook_key, include_deleted=True)
        target = plan["update"] if existing else plan["create"]
        target.append(hook_key)

        if not dry_run:
            save_hook(
                hook_key,
                hook.get("hook_group", ""),
                hook.get("hook_content", ""),
                hook.get("description", ""),
                hook.get("category", ""),
                hook.get("priority", 100),
                hook.get("is_active", True),
            )

    return plan
