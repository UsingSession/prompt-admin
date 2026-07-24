# Prompt Admin

Prompt Admin is a local, generic prompt-management service backed by
PostgreSQL. It owns application behavior, API and server-rendered UI contracts,
database migrations, tests, Docker image construction, and releases.

It does not own workflow graphs, model calls, Qdrant datasets,
project-specific records, or `UsingSession/localai` orchestration.

## Current implementation

Prompt Admin v2 Phase 4A provides:

- FastAPI application factory and Uvicorn runtime;
- lifespan-based PostgreSQL initialization and ordered migrations;
- explicit parameterized `psycopg` repositories and transactions;
- Prompt Family, Prompt, Prompt Variant, and immutable Prompt Revision API;
- server-rendered Prompt administration UI and Revision comparison;
- Deleted Records lifecycle for Families and Prompts;
- Hook metadata management API;
- immutable Hook Revision creation and history;
- concurrency-safe Prompt and Hook Revision numbering;
- deterministic Hook placeholder compilation;
- preview and strict compiler modes;
- read-only Prompt Revision compiled-preview endpoint;
- strict Pydantic request and response schemas;
- stable machine-readable errors;
- unit, API, and real PostgreSQL tests.

Hook administration UI, Bundles, publication, immutable Compiled Artifacts, the
final runtime Bundle API, ETag support, and import/export remain deferred.

## Local endpoints

Administration UI:

```text
http://localhost:8090/
```

FastAPI documentation:

```text
http://localhost:8090/docs
http://localhost:8090/openapi.json
```

Health check:

```http
GET /healthz
```

The service is local-only. Bind it to `127.0.0.1` through the infrastructure
repository. Authentication is required before LAN or public exposure.

## Configuration

```text
PROMPT_ADMIN_HOST=0.0.0.0
PROMPT_ADMIN_PORT=8090
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=local_password
```

Configuration is validated at startup. Database passwords are preserved
exactly and are not whitespace-normalized.

## Application entrypoint

```bash
uvicorn app:create_app --factory --host 0.0.0.0 --port 8090
```

## Architecture

API requests use:

```text
FastAPI API route
-> Pydantic boundary schema
-> domain or compiler service
-> explicit psycopg repository
-> PostgreSQL
```

Browser administration uses:

```text
FastAPI UI route
-> Pydantic form boundary
-> domain service
-> explicit psycopg repository
-> Jinja2 response or 303 redirect
```

UI handlers do not issue loopback HTTP calls or execute SQL. Core
administration works without JavaScript.

## Prompt domain

```text
Prompt Family
└─ Prompt
   └─ Prompt Variant
      ├─ Prompt Revision 1
      └─ Prompt Revision 2
```

Prompt rows contain metadata only. Prompt text is stored in immutable Prompt
Revisions. Variant statuses are:

```text
draft
available
archived
```

`production` belongs to a future published Bundle Revision, not a Variant.

Prompt management API:

```http
GET    /api/v1/families
POST   /api/v1/families
GET    /api/v1/families/{family_key}
PATCH  /api/v1/families/{family_key}
DELETE /api/v1/families/{family_key}
POST   /api/v1/families/{family_key}/restore

GET    /api/v1/prompts
POST   /api/v1/prompts
GET    /api/v1/prompts/{prompt_key}
PATCH  /api/v1/prompts/{prompt_key}
DELETE /api/v1/prompts/{prompt_key}
POST   /api/v1/prompts/{prompt_key}/restore

GET   /api/v1/prompts/{prompt_key}/variants
POST  /api/v1/prompts/{prompt_key}/variants
GET   /api/v1/prompts/{prompt_key}/variants/{variant_key}
PATCH /api/v1/prompts/{prompt_key}/variants/{variant_key}

GET  /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions
POST /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions
GET  /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions/{revision}
```

Prompt Revision update and delete routes do not exist.

## Hook domain

```text
Hook metadata
└─ immutable Hook Revisions
```

A Hook row stores:

```text
hook_key
display_name
description
category
created_at
updated_at
deleted_at
```

A Hook Revision stores:

```text
revision_number
hook_group
hook_content
priority
is_enabled
change_note
created_at
```

Hook management API:

```http
GET    /api/v1/hooks
POST   /api/v1/hooks
GET    /api/v1/hooks/{hook_key}
PATCH  /api/v1/hooks/{hook_key}
DELETE /api/v1/hooks/{hook_key}
POST   /api/v1/hooks/{hook_key}/restore

GET  /api/v1/hooks/{hook_key}/revisions
POST /api/v1/hooks/{hook_key}/revisions
GET  /api/v1/hooks/{hook_key}/revisions/{revision}
```

Hook Revision update and delete routes do not exist. Hook deletion is soft;
permanent deletion is not implemented in Phase 4A.

The effective Hook Revision is always the highest `revision_number`. The
compiler never falls back to an older enabled Revision. A disabled latest
Revision or deleted Hook contributes nothing.

Concurrent Hook Revision creation locks the Hook row with
`SELECT ... FOR UPDATE` before calculating and inserting the next number.

Detailed Hook documentation:

```text
docs/hook-domain-api.md
docs/hook-compiler.md
```

## Hook compiler

Prompt placeholders use:

```text
#hook_global.response_rules
```

The stored group omits `#`:

```text
hook_global.response_rules
```

The compiler:

1. scans placeholders left to right;
2. deduplicates detected-group metadata;
3. loads effective Revisions with one repository query;
4. orders contributors by `priority ASC`, then `hook_key ASC`;
5. joins contents using `\n\n`;
6. replaces every recognized occurrence without changing other text.

Preview mode preserves unresolved tokens and reports unresolved groups. Strict
mode fails with `unresolved_hook_groups` and returns no successful partial
result.

Prompt Revision compiled preview:

```http
GET /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions/
    {revision}/compiled-preview
```

The endpoint compiles an exact immutable Prompt Revision against current Hook
state. It is a mutable administration preview, not a published runtime artifact
or n8n production contract.

The low-level compiler accepts a caller-provided PostgreSQL cursor so future
Bundle publication can compile inside one publication transaction.

## Stable keys and validation

`family_key`, `prompt_key`, `variant_key`, and `hook_key` are immutable. The
application rejects empty keys, surrounding whitespace, values over 120
characters, and `_vN` Revision suffixes. Invalid values are not normalized.

Hook groups must match:

```text
hook_[A-Za-z0-9_.-]+
```

They are stored without a leading `#`. Hook content must contain visible
characters. Priority must be non-negative.

## Errors

API errors use:

```json
{
  "error": {
    "code": "hook_not_found",
    "message": "Hook was not found."
  }
}
```

Hook and compiler codes include:

```text
hook_not_found
hook_key_conflict
hook_deleted
hook_revision_not_found
hook_revision_conflict
invalid_hook_group
invalid_hook_priority
unresolved_hook_groups
database_unavailable
```

SQL, table names, raw PostgreSQL messages, connection details, stack traces,
and Prompt or Hook content are not exposed in normal responses or logs.

## Security

Browser writes validate `Origin`, or `Referer` when Origin is absent. Accepted
hosts are exact matches:

```text
localhost
127.0.0.1
::1
```

Prefix and subdomain values such as `localhost.evil.example` are rejected.
Requests without either header remain supported for local non-browser clients.
All responses include:

```text
Cache-Control: no-cache
```

## Database initialization

Startup applies `database/schema.sql`, then ordered files in
`database/migrations/`. The v2 baseline remains:

```text
database/migrations/005_prompt_model_v2.sql
```

Phase 4A requires no schema migration. Existing Hook tables and constraints are
used unchanged. Repeated startup is idempotent and concurrent startup is
serialized with a PostgreSQL advisory transaction lock.

## Tests

Install dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the complete suite against a dedicated PostgreSQL database:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Coverage includes Prompt API/UI regressions, Hook lifecycle and immutability,
concurrent Hook Revision creation, effective Revision selection, parser and
deterministic ordering, preview and strict modes, compiled preview, OpenAPI,
exact-origin safeguards, database startup, Docker build, and `/healthz`.

## UI scope

Active navigation remains:

```text
Dashboard
Prompts
Families
Deleted Records
FastAPI documentation
```

`/hooks` remains unregistered and returns the normal HTML `404` until Phase 4B.

## Removed pre-v2 routes

Pre-v2 routes such as `/api-docs`, `/api/prompts/compiled`, `/save`, and
`/delete` remain unregistered. No compatibility path is provided.

## Deferred work

- Phase 4B: Hook UI, Revision comparison, and impact views;
- Phase 5: Bundles, publication, immutable artifacts, and hashing;
- Phase 6: final Bundle runtime API and ETag support;
- Phase 7: v2 import/export and remaining administration UX;
- Phase 8: release, `localai` image pinning, and n8n migration.
