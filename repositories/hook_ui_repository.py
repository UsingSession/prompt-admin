from typing import Any

from psycopg import Cursor


HOOK_SUMMARY_COLUMNS = """
    h.hook_key,
    h.display_name,
    h.description,
    h.category,
    h.created_at,
    h.updated_at,
    h.deleted_at,
    latest.revision_number,
    latest.hook_group,
    latest.priority,
    latest.is_enabled,
    latest.change_note,
    latest.created_at AS revision_created_at
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


def list_hook_summaries(
    cursor: Cursor,
    category: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    conditions = []
    parameters: list[Any] = []
    if not include_deleted:
        conditions.append("h.deleted_at IS NULL")
    if category is not None:
        conditions.append("h.category = %s")
        parameters.append(category)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(
        f"""
        SELECT {HOOK_SUMMARY_COLUMNS}
        FROM ai_hooks h
        LEFT JOIN LATERAL (
            SELECT
                r.revision_number,
                r.hook_group,
                r.priority,
                r.is_enabled,
                r.change_note,
                r.created_at
            FROM ai_hook_revisions r
            WHERE r.hook_id = h.id
            ORDER BY r.revision_number DESC
            LIMIT 1
        ) latest ON TRUE
        {where_clause}
        ORDER BY h.hook_key ASC;
        """,
        parameters,
    )
    return _rows(cursor)


def get_hook_summary(cursor: Cursor, hook_key: str) -> dict | None:
    cursor.execute(
        f"""
        SELECT {HOOK_SUMMARY_COLUMNS}
        FROM ai_hooks h
        LEFT JOIN LATERAL (
            SELECT
                r.revision_number,
                r.hook_group,
                r.priority,
                r.is_enabled,
                r.change_note,
                r.created_at
            FROM ai_hook_revisions r
            WHERE r.hook_id = h.id
            ORDER BY r.revision_number DESC
            LIMIT 1
        ) latest ON TRUE
        WHERE h.hook_key = %s;
        """,
        (hook_key,),
    )
    return _row(cursor, cursor.fetchone())


def dashboard_counts(cursor: Cursor) -> dict:
    cursor.execute(
        """
        WITH latest_revisions AS (
            SELECT DISTINCT ON (r.hook_id)
                r.hook_id,
                r.is_enabled
            FROM ai_hook_revisions r
            ORDER BY r.hook_id, r.revision_number DESC
        )
        SELECT
            COUNT(*) FILTER (WHERE h.deleted_at IS NULL) AS active_count,
            COUNT(*) FILTER (
                WHERE h.deleted_at IS NULL
                  AND latest.hook_id IS NULL
            ) AS no_revision_count,
            COUNT(*) FILTER (
                WHERE h.deleted_at IS NULL
                  AND latest.is_enabled = FALSE
            ) AS disabled_count
        FROM ai_hooks h
        LEFT JOIN latest_revisions latest ON latest.hook_id = h.id;
        """
    )
    return _row(cursor, cursor.fetchone())


def list_group_latest_revisions(
    cursor: Cursor,
    hook_group: str,
) -> list[dict]:
    cursor.execute(
        """
        WITH latest_revisions AS (
            SELECT DISTINCT ON (r.hook_id)
                r.hook_id,
                r.revision_number,
                r.hook_group,
                r.priority,
                r.is_enabled,
                r.created_at
            FROM ai_hook_revisions r
            ORDER BY r.hook_id, r.revision_number DESC
        )
        SELECT
            h.hook_key,
            h.display_name,
            h.deleted_at,
            latest.revision_number,
            latest.hook_group,
            latest.priority,
            latest.is_enabled,
            latest.created_at
        FROM latest_revisions latest
        JOIN ai_hooks h ON h.id = latest.hook_id
        WHERE latest.hook_group = %s
        ORDER BY latest.priority ASC, h.hook_key ASC;
        """,
        (hook_group,),
    )
    return _rows(cursor)
