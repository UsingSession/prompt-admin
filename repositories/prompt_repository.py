from psycopg import Cursor


def prompt_exists(cursor: Cursor, prompt_id: int) -> bool:
    cursor.execute(
        "SELECT 1 FROM ai_prompts WHERE id = %s;",
        (prompt_id,),
    )
    return cursor.fetchone() is not None


def prompt_revision_exists(cursor: Cursor, revision_id: int) -> bool:
    cursor.execute(
        "SELECT 1 FROM ai_prompt_revisions WHERE id = %s;",
        (revision_id,),
    )
    return cursor.fetchone() is not None


def next_prompt_revision_number(cursor: Cursor, variant_id: int) -> int:
    cursor.execute(
        """
        SELECT COALESCE(MAX(revision_number), 0) + 1
        FROM ai_prompt_revisions
        WHERE variant_id = %s;
        """,
        (variant_id,),
    )
    return cursor.fetchone()[0]
