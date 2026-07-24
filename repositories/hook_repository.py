from collections.abc import Mapping, Sequence
from typing import Any

from psycopg import Cursor


HOOK_COLUMNS = """
    hook_key,
    display_name,
    description,
    category,
    created_at,
    updated_at,
    deleted_at
"""
REVISION_COLUMNS = """
    h.hook_key,
    r.revision_number,
    r.hook_group,
    r.hook_content,
    r.priority,
    r.is_enabled,
    r.change_note,
    r.created_at
"""


def _row(cursor: Cursor, value: tuple[Any, ...] | None) -> dict | None:
    if value is None:
        return None
    return {
        column.name: item
        for column, item in zip(cursor.description, value, strict=True)
    }


def _rows(cursor: Cursor) -> list[dict]:
    return [
        {
            column.name: item
            for column, item in zip(cursor.description, value, strict=True)
        }
        for value in cursor.fetchall()
    ]


def hook_exists(cursor: Cursor, hook_id: int) -> bool:
    cursor.execute("SELECT 1 FROM ai_hooks WHERE id = %s;", (hook_id,))
    return cursor.fetchone() is not None


def create_hook(
    cursor: Cursor,
    hook_key: str,
    display_name: str,
    description: str,
    category: str,
) -> dict:
    cursor.execute(
        f"""
        INSERT INTO ai_hooks (
            hook_key,
            display_name,
            description,
            category
        )
        VALUES (%s, %s, %s, %s)
        RETURNING {HOOK_COLUMNS};
        """,
        (hook_key, display_name, description, category),
    )
    return _row(cursor, cursor.fetchone())


def get_hook(
    cursor: Cursor,
    hook_key: str,
    include_deleted: bool = False,
    lock: bool = False,
) -> dict | None:
    deleted_clause = "" if include_deleted else "AND deleted_at IS NULL"
    lock_clause = "FOR UPDATE" if lock else ""
    cursor.execute(
        f"""
        SELECT {HOOK_COLUMNS}
        FROM ai_hooks
        WHERE hook_key = %s
          {deleted_clause}
        {lock_clause};
        """,
        (hook_key,),
    )
    return _row(cursor, cursor.fetchone())


def get_hook_state(
    cursor: Cursor,
    hook_key: str,
    lock: bool = False,
) -> dict | None:
    lock_clause = "FOR UPDATE" if lock else ""
    cursor.execute(
        f"""
        SELECT id, deleted_at
        FROM ai_hooks
        WHERE hook_key = %s
        {lock_clause};
        """,
        (hook_key,),
    )
    return _row(cursor, cursor.fetchone())


def list_hooks(
    cursor: Cursor,
    category: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    conditions = []
    parameters: list[Any] = []
    if not include_deleted:
        conditions.append("deleted_at IS NULL")
    if category is not None:
        conditions.append("category = %s")
        parameters.append(category)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cursor.execute(
        f"""
        SELECT {HOOK_COLUMNS}
        FROM ai_hooks
        {where_clause}
        ORDER BY hook_key ASC;
        """,
        parameters,
    )
    return _rows(cursor)


def update_hook(
    cursor: Cursor,
    hook_key: str,
    values: Mapping[str, Any],
) -> dict | None:
    assignments = [f"{name} = %s" for name in values]
    parameters = list(values.values())
    assignments.append("updated_at = NOW()")
    parameters.append(hook_key)
    cursor.execute(
        f"""
        UPDATE ai_hooks
        SET {', '.join(assignments)}
        WHERE hook_key = %s
          AND deleted_at IS NULL
        RETURNING {HOOK_COLUMNS};
        """,
        parameters,
    )
    return _row(cursor, cursor.fetchone())


def soft_delete_hook(cursor: Cursor, hook_key: str) -> bool:
    cursor.execute(
        """
        UPDATE ai_hooks
        SET deleted_at = NOW(), updated_at = NOW()
        WHERE hook_key = %s
          AND deleted_at IS NULL;
        """,
        (hook_key,),
    )
    return cursor.rowcount == 1


def restore_hook(cursor: Cursor, hook_key: str) -> dict | None:
    cursor.execute(
        f"""
        UPDATE ai_hooks
        SET deleted_at = NULL, updated_at = NOW()
        WHERE hook_key = %s
          AND deleted_at IS NOT NULL
        RETURNING {HOOK_COLUMNS};
        """,
        (hook_key,),
    )
    return _row(cursor, cursor.fetchone())


def next_hook_revision_number(cursor: Cursor, hook_id: int) -> int:
    cursor.execute(
        """
        SELECT COALESCE(MAX(revision_number), 0) + 1
        FROM ai_hook_revisions
        WHERE hook_id = %s;
        """,
        (hook_id,),
    )
    return cursor.fetchone()[0]


def create_revision(
    cursor: Cursor,
    hook_id: int,
    revision_number: int,
    hook_group: str,
    hook_content: str,
    priority: int,
    is_enabled: bool,
    change_note: str,
) -> dict:
    cursor.execute(
        """
        INSERT INTO ai_hook_revisions (
            hook_id,
            revision_number,
            hook_group,
            hook_content,
            priority,
            is_enabled,
            change_note
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (
            hook_id,
            revision_number,
            hook_group,
            hook_content,
            priority,
            is_enabled,
            change_note,
        ),
    )
    return get_revision_by_id(cursor, cursor.fetchone()[0])


def get_revision_by_id(cursor: Cursor, revision_id: int) -> dict:
    cursor.execute(
        f"""
        SELECT {REVISION_COLUMNS}
        FROM ai_hook_revisions r
        JOIN ai_hooks h ON h.id = r.hook_id
        WHERE r.id = %s;
        """,
        (revision_id,),
    )
    return _row(cursor, cursor.fetchone())


def get_revision(
    cursor: Cursor,
    hook_key: str,
    revision_number: int,
) -> dict | None:
    cursor.execute(
        f"""
        SELECT {REVISION_COLUMNS}
        FROM ai_hook_revisions r
        JOIN ai_hooks h ON h.id = r.hook_id
        WHERE h.hook_key = %s
          AND r.revision_number = %s;
        """,
        (hook_key, revision_number),
    )
    return _row(cursor, cursor.fetchone())


def list_revisions(cursor: Cursor, hook_key: str) -> list[dict]:
    cursor.execute(
        f"""
        SELECT {REVISION_COLUMNS}
        FROM ai_hook_revisions r
        JOIN ai_hooks h ON h.id = r.hook_id
        WHERE h.hook_key = %s
        ORDER BY r.revision_number ASC;
        """,
        (hook_key,),
    )
    return _rows(cursor)


def load_effective_hook_revisions(
    cursor: Cursor,
    hook_groups: Sequence[str],
) -> list[dict]:
    if not hook_groups:
        return []

    groups = list(hook_groups)
    cursor.execute(
        """
        WITH latest_revisions AS (
            SELECT DISTINCT ON (r.hook_id)
                r.hook_id,
                r.revision_number,
                r.hook_group,
                r.hook_content,
                r.priority,
                r.is_enabled
            FROM ai_hook_revisions r
            JOIN ai_hooks h ON h.id = r.hook_id
            WHERE h.deleted_at IS NULL
            ORDER BY r.hook_id, r.revision_number DESC
        )
        SELECT
            h.hook_key,
            latest.revision_number,
            latest.hook_group,
            latest.hook_content,
            latest.priority
        FROM latest_revisions latest
        JOIN ai_hooks h ON h.id = latest.hook_id
        WHERE latest.hook_group = ANY(%s)
          AND latest.is_enabled = TRUE
        ORDER BY
            array_position(%s::text[], latest.hook_group),
            latest.priority ASC,
            h.hook_key ASC;
        """,
        (groups, groups),
    )
    return _rows(cursor)
