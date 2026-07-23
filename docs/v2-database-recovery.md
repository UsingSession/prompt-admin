# Prompt Admin v2 Database Recovery

## Scope

Use this procedure only when Prompt Admin v2 startup reports that domain tables
exist without migration metadata, or migration metadata exists while required
v2 tables are missing.

Prompt Admin and n8n currently use the same PostgreSQL database and `public`
schema in the LocalAI stack. Do not drop the complete database or the PostgreSQL
volume. That would remove n8n state as well.

The PostgreSQL database was intentionally cleared of Prompt Admin data before
Phase 2. This recovery procedure does not migrate or preserve Prompt Admin
records.

## Typical error

```text
Cannot apply 005_prompt_model_v2.sql: Prompt Admin v2 tables exist without
migration metadata: ai_hooks. Reset the incomplete Prompt Admin v2 schema
before restarting the application.
```

Earlier builds may report only:

```text
relation "ai_hooks" already exists
```

## Cause

The migration metadata row and the Prompt Admin v2 domain tables are not in a
consistent state.

Possible causes include:

- an earlier manual schema attempt;
- v2 tables created outside the migration runner;
- a partially prepared development database;
- an older build without serialized startup migrations.

Current startup acquires a PostgreSQL advisory transaction lock before schema
initialization. Concurrent Prompt Admin processes therefore cannot apply the
same migration simultaneously.

## Inspect the current state

Stop Prompt Admin before changing the schema:

```bash
docker compose stop prompt-admin
```

Inspect Prompt Admin v2 tables:

```sql
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'ai_prompt_families',
    'ai_prompts',
    'ai_prompt_variants',
    'ai_prompt_revisions',
    'ai_hooks',
    'ai_hook_revisions',
    'ai_prompt_bundles',
    'ai_prompt_bundle_revisions',
    'ai_prompt_bundle_items',
    'ai_compiled_bundle_artifacts'
  )
ORDER BY tablename;
```

Inspect migration metadata:

```sql
SELECT migration_name, applied_at
FROM prompt_admin_migrations
ORDER BY applied_at;
```

## Reset only the incomplete Prompt Admin v2 schema

The statements deliberately omit `CASCADE`. If another table unexpectedly
references a Prompt Admin table, PostgreSQL will stop instead of silently
removing unrelated data.

```sql
BEGIN;

DROP TABLE IF EXISTS ai_compiled_bundle_artifacts;
DROP TABLE IF EXISTS ai_prompt_bundle_items;
DROP TABLE IF EXISTS ai_prompt_bundle_revisions;
DROP TABLE IF EXISTS ai_prompt_bundles;
DROP TABLE IF EXISTS ai_hook_revisions;
DROP TABLE IF EXISTS ai_hooks;
DROP TABLE IF EXISTS ai_prompt_revisions;
DROP TABLE IF EXISTS ai_prompt_variants;
DROP TABLE IF EXISTS ai_prompts;
DROP TABLE IF EXISTS ai_prompt_families;

DELETE FROM prompt_admin_migrations
WHERE migration_name = '005_prompt_model_v2.sql';

COMMIT;
```

Do not remove n8n tables or the PostgreSQL volume.

## Restart and verify

Recreate Prompt Admin with the updated image or development build:

```bash
docker compose up -d --force-recreate prompt-admin
```

Inspect startup logs:

```bash
docker compose logs --tail=100 prompt-admin
```

Verify health:

```text
http://localhost:8090/healthz
```

Expected response:

```json
{
  "status": "ok",
  "database": true
}
```

The legacy administration routes intentionally return HTTP `503` during Phase
2. Only `/healthz` is expected to remain operational until Phase 3 introduces
v2 domain routes.
