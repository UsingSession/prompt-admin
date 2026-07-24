from typing import Any

from psycopg import Cursor


def _rows(cursor: Cursor) -> list[dict]:
    return [
        {
            column.name: item
            for column, item in zip(cursor.description, value, strict=True)
        }
        for value in cursor.fetchall()
    ]


def list_prompt_revision_candidates(
    cursor: Cursor,
    placeholder: str,
) -> list[dict]:
    cursor.execute(
        """
        SELECT
            p.prompt_key,
            v.variant_key,
            v.status AS variant_status,
            r.revision_number,
            r.created_at,
            r.system_prompt,
            r.revision_number = MAX(r.revision_number) OVER (
                PARTITION BY v.id
            ) AS is_latest_revision
        FROM ai_prompt_revisions r
        JOIN ai_prompt_variants v ON v.id = r.variant_id
        JOIN ai_prompts p ON p.id = v.prompt_id
        WHERE p.deleted_at IS NULL
          AND v.deleted_at IS NULL
          AND POSITION(%s IN r.system_prompt) > 0
        ORDER BY
            p.prompt_key ASC,
            v.variant_key ASC,
            r.revision_number ASC;
        """,
        (placeholder,),
    )
    return _rows(cursor)
