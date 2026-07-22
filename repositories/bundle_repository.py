from psycopg import Cursor


def bundle_exists(cursor: Cursor, bundle_id: int) -> bool:
    cursor.execute(
        "SELECT 1 FROM ai_prompt_bundles WHERE id = %s;",
        (bundle_id,),
    )
    return cursor.fetchone() is not None


def bundle_revision_exists(cursor: Cursor, revision_id: int) -> bool:
    cursor.execute(
        "SELECT 1 FROM ai_prompt_bundle_revisions WHERE id = %s;",
        (revision_id,),
    )
    return cursor.fetchone() is not None


def next_bundle_revision_number(cursor: Cursor, bundle_id: int) -> int:
    cursor.execute(
        """
        SELECT COALESCE(MAX(revision_number), 0) + 1
        FROM ai_prompt_bundle_revisions
        WHERE bundle_id = %s;
        """,
        (bundle_id,),
    )
    return cursor.fetchone()[0]
