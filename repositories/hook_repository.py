from psycopg import Cursor


def hook_exists(cursor: Cursor, hook_id: int) -> bool:
    cursor.execute(
        "SELECT 1 FROM ai_hooks WHERE id = %s;",
        (hook_id,),
    )
    return cursor.fetchone() is not None


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
