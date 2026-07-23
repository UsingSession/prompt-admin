from collections.abc import Mapping
from typing import Any

from psycopg import Cursor


FAMILY_COLUMNS = """
    family_key,
    display_name,
    description,
    created_at,
    updated_at,
    deleted_at
"""
PROMPT_COLUMNS = """
    p.prompt_key,
    p.display_name,
    p.description,
    p.category,
    f.family_key,
    p.created_at,
    p.updated_at,
    p.deleted_at
"""
VARIANT_COLUMNS = """
    p.prompt_key,
    v.variant_key,
    v.display_name,
    v.description,
    v.status,
    v.created_at,
    v.updated_at
"""
REVISION_COLUMNS = """
    p.prompt_key,
    v.variant_key,
    r.revision_number,
    r.system_prompt,
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


def prompt_exists(cursor: Cursor, prompt_id: int) -> bool:
    cursor.execute("SELECT 1 FROM ai_prompts WHERE id = %s;", (prompt_id,))
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


def create_family(
    cursor: Cursor,
    family_key: str,
    display_name: str,
    description: str,
) -> dict:
    cursor.execute(
        f"""
        INSERT INTO ai_prompt_families (
            family_key,
            display_name,
            description
        )
        VALUES (%s, %s, %s)
        RETURNING {FAMILY_COLUMNS};
        """,
        (family_key, display_name, description),
    )
    return _row(cursor, cursor.fetchone())


def get_family(
    cursor: Cursor,
    family_key: str,
    include_deleted: bool = False,
    lock: bool = False,
) -> dict | None:
    deleted_clause = "" if include_deleted else "AND deleted_at IS NULL"
    lock_clause = "FOR UPDATE" if lock else ""
    cursor.execute(
        f"""
        SELECT {FAMILY_COLUMNS}
        FROM ai_prompt_families
        WHERE family_key = %s
          {deleted_clause}
        {lock_clause};
        """,
        (family_key,),
    )
    return _row(cursor, cursor.fetchone())


def get_family_id(
    cursor: Cursor,
    family_key: str,
    lock: bool = False,
) -> dict | None:
    lock_clause = "FOR SHARE" if lock else ""
    cursor.execute(
        f"""
        SELECT id, deleted_at
        FROM ai_prompt_families
        WHERE family_key = %s
        {lock_clause};
        """,
        (family_key,),
    )
    return _row(cursor, cursor.fetchone())


def list_families(cursor: Cursor, include_deleted: bool = False) -> list[dict]:
    deleted_clause = "" if include_deleted else "WHERE deleted_at IS NULL"
    cursor.execute(
        f"""
        SELECT {FAMILY_COLUMNS}
        FROM ai_prompt_families
        {deleted_clause}
        ORDER BY family_key ASC;
        """
    )
    return _rows(cursor)


def update_family(
    cursor: Cursor,
    family_key: str,
    values: Mapping[str, Any],
) -> dict | None:
    assignments = [f"{name} = %s" for name in values]
    parameters = list(values.values())
    assignments.append("updated_at = NOW()")
    parameters.append(family_key)
    cursor.execute(
        f"""
        UPDATE ai_prompt_families
        SET {', '.join(assignments)}
        WHERE family_key = %s
          AND deleted_at IS NULL
        RETURNING {FAMILY_COLUMNS};
        """,
        parameters,
    )
    return _row(cursor, cursor.fetchone())


def soft_delete_family(cursor: Cursor, family_key: str) -> bool:
    cursor.execute(
        """
        UPDATE ai_prompt_families
        SET deleted_at = NOW(), updated_at = NOW()
        WHERE family_key = %s
          AND deleted_at IS NULL;
        """,
        (family_key,),
    )
    return cursor.rowcount == 1


def restore_family(cursor: Cursor, family_key: str) -> dict | None:
    cursor.execute(
        f"""
        UPDATE ai_prompt_families
        SET deleted_at = NULL, updated_at = NOW()
        WHERE family_key = %s
          AND deleted_at IS NOT NULL
        RETURNING {FAMILY_COLUMNS};
        """,
        (family_key,),
    )
    return _row(cursor, cursor.fetchone())


def create_prompt(
    cursor: Cursor,
    prompt_key: str,
    display_name: str,
    description: str,
    category: str,
    family_id: int | None,
) -> dict:
    cursor.execute(
        """
        INSERT INTO ai_prompts (
            prompt_key,
            display_name,
            description,
            category,
            prompt_family_id
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (prompt_key, display_name, description, category, family_id),
    )
    prompt_id = cursor.fetchone()[0]
    return get_prompt_by_id(cursor, prompt_id)


def get_prompt_by_id(cursor: Cursor, prompt_id: int) -> dict:
    cursor.execute(
        f"""
        SELECT {PROMPT_COLUMNS}
        FROM ai_prompts p
        LEFT JOIN ai_prompt_families f ON f.id = p.prompt_family_id
        WHERE p.id = %s;
        """,
        (prompt_id,),
    )
    return _row(cursor, cursor.fetchone())


def get_prompt(
    cursor: Cursor,
    prompt_key: str,
    include_deleted: bool = False,
    lock: bool = False,
) -> dict | None:
    deleted_clause = "" if include_deleted else "AND p.deleted_at IS NULL"
    lock_clause = "FOR UPDATE OF p" if lock else ""
    cursor.execute(
        f"""
        SELECT {PROMPT_COLUMNS}
        FROM ai_prompts p
        LEFT JOIN ai_prompt_families f ON f.id = p.prompt_family_id
        WHERE p.prompt_key = %s
          {deleted_clause}
        {lock_clause};
        """,
        (prompt_key,),
    )
    return _row(cursor, cursor.fetchone())


def get_prompt_state(
    cursor: Cursor,
    prompt_key: str,
    lock: bool = False,
) -> dict | None:
    lock_clause = "FOR UPDATE" if lock else ""
    cursor.execute(
        f"""
        SELECT id, deleted_at
        FROM ai_prompts
        WHERE prompt_key = %s
        {lock_clause};
        """,
        (prompt_key,),
    )
    return _row(cursor, cursor.fetchone())


def list_prompts(
    cursor: Cursor,
    family_key: str | None = None,
    category: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    conditions = []
    parameters: list[Any] = []
    if not include_deleted:
        conditions.append("p.deleted_at IS NULL")
    if family_key is not None:
        conditions.append("f.family_key = %s")
        parameters.append(family_key)
    if category is not None:
        conditions.append("p.category = %s")
        parameters.append(category)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cursor.execute(
        f"""
        SELECT {PROMPT_COLUMNS}
        FROM ai_prompts p
        LEFT JOIN ai_prompt_families f ON f.id = p.prompt_family_id
        {where_clause}
        ORDER BY p.prompt_key ASC;
        """,
        parameters,
    )
    return _rows(cursor)


def update_prompt(
    cursor: Cursor,
    prompt_key: str,
    values: Mapping[str, Any],
) -> dict | None:
    assignments = [f"{name} = %s" for name in values]
    parameters = list(values.values())
    assignments.append("updated_at = NOW()")
    parameters.append(prompt_key)
    cursor.execute(
        f"""
        UPDATE ai_prompts
        SET {', '.join(assignments)}
        WHERE prompt_key = %s
          AND deleted_at IS NULL
        RETURNING id;
        """,
        parameters,
    )
    value = cursor.fetchone()
    return None if value is None else get_prompt_by_id(cursor, value[0])


def soft_delete_prompt(cursor: Cursor, prompt_key: str) -> bool:
    cursor.execute(
        """
        UPDATE ai_prompts
        SET deleted_at = NOW(), updated_at = NOW()
        WHERE prompt_key = %s
          AND deleted_at IS NULL;
        """,
        (prompt_key,),
    )
    return cursor.rowcount == 1


def restore_prompt(cursor: Cursor, prompt_key: str) -> dict | None:
    cursor.execute(
        """
        UPDATE ai_prompts
        SET deleted_at = NULL, updated_at = NOW()
        WHERE prompt_key = %s
          AND deleted_at IS NOT NULL
        RETURNING id;
        """,
        (prompt_key,),
    )
    value = cursor.fetchone()
    return None if value is None else get_prompt_by_id(cursor, value[0])


def create_variant(
    cursor: Cursor,
    prompt_id: int,
    variant_key: str,
    display_name: str,
    description: str,
    status: str,
) -> dict:
    cursor.execute(
        """
        INSERT INTO ai_prompt_variants (
            prompt_id,
            variant_key,
            display_name,
            description,
            status
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (prompt_id, variant_key, display_name, description, status),
    )
    return get_variant_by_id(cursor, cursor.fetchone()[0])


def get_variant_by_id(cursor: Cursor, variant_id: int) -> dict:
    cursor.execute(
        f"""
        SELECT {VARIANT_COLUMNS}
        FROM ai_prompt_variants v
        JOIN ai_prompts p ON p.id = v.prompt_id
        WHERE v.id = %s;
        """,
        (variant_id,),
    )
    return _row(cursor, cursor.fetchone())


def get_variant(
    cursor: Cursor,
    prompt_key: str,
    variant_key: str,
    lock: bool = False,
) -> dict | None:
    lock_clause = "FOR UPDATE OF v" if lock else ""
    cursor.execute(
        f"""
        SELECT {VARIANT_COLUMNS}
        FROM ai_prompt_variants v
        JOIN ai_prompts p ON p.id = v.prompt_id
        WHERE p.prompt_key = %s
          AND v.variant_key = %s
          AND v.deleted_at IS NULL
        {lock_clause};
        """,
        (prompt_key, variant_key),
    )
    return _row(cursor, cursor.fetchone())


def get_variant_state(
    cursor: Cursor,
    prompt_id: int,
    variant_key: str,
    lock: bool = False,
) -> dict | None:
    lock_clause = "FOR UPDATE" if lock else ""
    cursor.execute(
        f"""
        SELECT id, status, deleted_at
        FROM ai_prompt_variants
        WHERE prompt_id = %s
          AND variant_key = %s
        {lock_clause};
        """,
        (prompt_id, variant_key),
    )
    return _row(cursor, cursor.fetchone())


def list_variants(cursor: Cursor, prompt_key: str) -> list[dict]:
    cursor.execute(
        f"""
        SELECT {VARIANT_COLUMNS}
        FROM ai_prompt_variants v
        JOIN ai_prompts p ON p.id = v.prompt_id
        WHERE p.prompt_key = %s
          AND v.deleted_at IS NULL
        ORDER BY v.variant_key ASC;
        """,
        (prompt_key,),
    )
    return _rows(cursor)


def update_variant(
    cursor: Cursor,
    prompt_id: int,
    variant_key: str,
    values: Mapping[str, Any],
) -> dict | None:
    assignments = [f"{name} = %s" for name in values]
    parameters = list(values.values())
    assignments.append("updated_at = NOW()")
    parameters.extend((prompt_id, variant_key))
    cursor.execute(
        f"""
        UPDATE ai_prompt_variants
        SET {', '.join(assignments)}
        WHERE prompt_id = %s
          AND variant_key = %s
          AND deleted_at IS NULL
        RETURNING id;
        """,
        parameters,
    )
    value = cursor.fetchone()
    return None if value is None else get_variant_by_id(cursor, value[0])


def create_revision(
    cursor: Cursor,
    variant_id: int,
    revision_number: int,
    system_prompt: str,
    change_note: str,
) -> dict:
    cursor.execute(
        """
        INSERT INTO ai_prompt_revisions (
            variant_id,
            revision_number,
            system_prompt,
            change_note
        )
        VALUES (%s, %s, %s, %s)
        RETURNING id;
        """,
        (variant_id, revision_number, system_prompt, change_note),
    )
    return get_revision_by_id(cursor, cursor.fetchone()[0])


def get_revision_by_id(cursor: Cursor, revision_id: int) -> dict:
    cursor.execute(
        f"""
        SELECT {REVISION_COLUMNS}
        FROM ai_prompt_revisions r
        JOIN ai_prompt_variants v ON v.id = r.variant_id
        JOIN ai_prompts p ON p.id = v.prompt_id
        WHERE r.id = %s;
        """,
        (revision_id,),
    )
    return _row(cursor, cursor.fetchone())


def get_revision(
    cursor: Cursor,
    prompt_key: str,
    variant_key: str,
    revision_number: int,
) -> dict | None:
    cursor.execute(
        f"""
        SELECT {REVISION_COLUMNS}
        FROM ai_prompt_revisions r
        JOIN ai_prompt_variants v ON v.id = r.variant_id
        JOIN ai_prompts p ON p.id = v.prompt_id
        WHERE p.prompt_key = %s
          AND v.variant_key = %s
          AND r.revision_number = %s;
        """,
        (prompt_key, variant_key, revision_number),
    )
    return _row(cursor, cursor.fetchone())


def list_revisions(
    cursor: Cursor,
    prompt_key: str,
    variant_key: str,
) -> list[dict]:
    cursor.execute(
        f"""
        SELECT {REVISION_COLUMNS}
        FROM ai_prompt_revisions r
        JOIN ai_prompt_variants v ON v.id = r.variant_id
        JOIN ai_prompts p ON p.id = v.prompt_id
        WHERE p.prompt_key = %s
          AND v.variant_key = %s
        ORDER BY r.revision_number ASC;
        """,
        (prompt_key, variant_key),
    )
    return _rows(cursor)
