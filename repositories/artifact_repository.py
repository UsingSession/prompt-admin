from psycopg import Cursor


def artifact_exists_for_bundle_revision(
    cursor: Cursor,
    bundle_revision_id: int,
) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM ai_compiled_bundle_artifacts
        WHERE bundle_revision_id = %s;
        """,
        (bundle_revision_id,),
    )
    return cursor.fetchone() is not None
