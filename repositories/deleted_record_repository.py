from psycopg import Cursor


def permanently_delete_family(cursor: Cursor, family_key: str) -> bool:
    """Delete one already soft-deleted Family."""
    cursor.execute(
        """
        DELETE FROM ai_prompt_families
        WHERE family_key = %s
          AND deleted_at IS NOT NULL;
        """,
        (family_key,),
    )
    return cursor.rowcount == 1


def prompt_has_referenced_revisions(
    cursor: Cursor,
    prompt_id: int,
) -> bool:
    """Return whether a Bundle item references any Prompt Revision."""
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM ai_prompt_bundle_items bi
            JOIN ai_prompt_revisions r
              ON r.id = bi.prompt_revision_id
            JOIN ai_prompt_variants v
              ON v.id = r.variant_id
            WHERE v.prompt_id = %s
        );
        """,
        (prompt_id,),
    )
    return bool(cursor.fetchone()[0])


def permanently_delete_prompt(cursor: Cursor, prompt_id: int) -> bool:
    """Delete one soft-deleted Prompt and its unreferenced history."""
    cursor.execute(
        """
        DELETE FROM ai_prompt_revisions
        WHERE variant_id IN (
            SELECT id
            FROM ai_prompt_variants
            WHERE prompt_id = %s
        );
        """,
        (prompt_id,),
    )
    cursor.execute(
        """
        DELETE FROM ai_prompt_variants
        WHERE prompt_id = %s;
        """,
        (prompt_id,),
    )
    cursor.execute(
        """
        DELETE FROM ai_prompts
        WHERE id = %s
          AND deleted_at IS NOT NULL;
        """,
        (prompt_id,),
    )
    return cursor.rowcount == 1
