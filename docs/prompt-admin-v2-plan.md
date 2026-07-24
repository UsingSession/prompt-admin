# Prompt Admin v2 Upgrade Plan

**Status:** accepted architecture and active implementation plan  
**Target repository:** `UsingSession/prompt-admin`  
**Related platform:** `UsingSession/localai`  
**Prepared:** 2026-07-22  
**Last updated:** 2026-07-24

## Implementation progress

### Phase 1 — FastAPI foundation

**Status:** completed and merged through PR #3,
`Add FastAPI foundation`.

Delivered FastAPI, Uvicorn, the application factory, lifespan startup,
`/healthz`, common errors, static files, exact local-origin safeguards, and
GitHub Actions validation.

### Phase 2 — Prompt Admin v2 database schema

**Status:** completed and merged through PR #4.

Delivered the clean v2 PostgreSQL schema, ordered migrations,
`db.transaction()`, advisory locking, schema-state validation, and startup and
migration tests. No pre-v2 data migration or compatibility path is supported.

### Phase 3A — Prompt domain API

**Status:** completed and merged through PR #5,
`Add Prompt Admin v2 prompt domain API`.

Verified history:

```text
final validated PR head: fbc2231dea1a5e99ae1f90445cf4ace919403ec3
merge commit:            4bd628cb20277da43521a8626b1f61f6ce7f5863
```

Delivered Prompt Family, Prompt, Variant, and immutable Prompt Revision API,
strict schemas, stable errors, explicit repositories, and concurrency-safe
Revision numbering.

### Phase 3B — Prompt administration UI

**Status:** completed and merged through PR #6,
`Add Prompt Admin v2 management UI`.

Verified history:

```text
final PR head: a4816727bcff58b0c360e42a9dbfbe03d4bb9aa3
merge commit:  835a5a1ed47cd624579532dbad86a28c80fe5145
```

Delivered the server-rendered Prompt administration UI, Revision comparison,
Deleted Records lifecycle, guarded permanent deletion, and Prompt API/UI
regression coverage.

The maintainer completed manual desktop and narrow-viewport inspection after
the automated validation. The server-rendered administration flows and
responsive layouts were accepted before proceeding to Phase 4.

### Phase 4A — Hook backend and compiler

**Status:** implementation in progress.

Branch:

```text
agent/hook-domain-compiler
```

Base:

```text
d7f296349b5524f9838078fd7470b5f7a726f1a0
```

The branch adds:

- Hook metadata create, list, read, update, soft delete, and restore API;
- immutable Hook Revision create, list, and read API;
- concurrency-safe sequential Hook Revision numbering;
- deterministic effective-Revision selection;
- preview and strict compilation modes;
- Prompt Revision compiled-preview endpoint;
- strict Hook and compiler schemas;
- stable Hook and compiler errors;
- unit, API, and real PostgreSQL tests;
- Hook domain and compiler documentation.

Do not mark Phase 4A completed until the full suite, real PostgreSQL Hook tests,
concurrent Revision creation, deterministic compiler behavior, compiled preview,
OpenAPI, Prompt API/UI regressions, startup checks, Docker build, and
`/healthz` have passed.

### Phase 4B — Hook UI and impact views

**Status:** pending.

Deliverables:

- Hook administration pages;
- immutable Hook Revision detail and comparison UI;
- Hook group and Prompt impact views;
- compiled-preview UI;
- active Hooks navigation.

### Phase 5 — Bundles and publication

**Status:** pending.

Deliverables include Bundle CRUD, draft Bundle Revisions, role mappings,
transactional publication, immutable Compiled Artifacts, and SHA-256 hashing.

### Phase 6 — Runtime API

**Status:** pending.

Deliverables include published Bundle retrieval, historical artifact retrieval,
stable runtime errors, ETag, and `If-None-Match`.

### Phase 7 — Import, export, and administration UX

**Status:** pending.

Deliverables include versioned export, dry-run import, transactional import,
additional filters, and remaining impact views.

### Phase 8 — Release and integration

**Status:** pending.

Deliverables include release notes, a versioned Docker image, `localai` image
pinning, n8n migration, smoke tests, and backup and restore verification.

## Purpose

Prompt Admin is a generic prompt-management service for multiple runtime
consumers. It owns prompt, hook, bundle, compilation, publication, and
application contracts. It does not own workflow sequencing, model calls,
Qdrant retrieval, retries, or project-specific records.

## Repository boundaries

### `UsingSession/prompt-admin`

Owns:

- application UI and API;
- Prompt, Hook, Bundle, Revision, and publication behavior;
- PostgreSQL schema and migrations;
- tests, Dockerfile, GitHub Actions, and releases;
- compiler and immutable artifact contracts.

### `UsingSession/localai`

Owns:

- Docker Compose and networking;
- PostgreSQL service configuration;
- Prompt Admin image pinning;
- backups and restore tooling;
- n8n runtime wiring.

### Project-specific repositories

Own actual Prompt and Hook records, Hook groups, Bundle definitions, workflows,
datasets, and domain-specific configuration.

## Accepted decisions

1. Pre-v2 data and HTTP compatibility are not required.
2. FastAPI and Uvicorn own the HTTP application layer.
3. Jinja2, plain CSS, and limited vanilla JavaScript own the UI.
4. PostgreSQL access remains explicit through `psycopg` repositories.
5. No ORM, Alembic, or frontend framework is required.
6. Prompt and Hook Revisions are immutable.
7. Stable keys never encode application-generated Revision suffixes.
8. Bundles are the future runtime unit.
9. Bundle publication pins exact Prompt Revisions and materializes artifacts.
10. Unresolved Hooks block publication.
11. Runtime consumers use Prompt Admin APIs, never its database tables.
12. n8n retains workflow sequencing and business logic.

## Current application structure

```text
app.py
-> application creation, middleware, exceptions, static files

routes.py
-> UI routers, Prompt API, Hook API, compiler preview, /healthz

api/prompt_management.py
-> Prompt management API

api/hook_management.py
-> Hook and immutable Hook Revision API

api/prompt_compilation.py
-> read-only Prompt Revision compiled preview

schemas/prompt.py
-> Prompt boundary schemas and stable-key validation

schemas/hook.py
-> Hook metadata, Hook group, and Hook Revision schemas

schemas/compiler.py
-> compiler response schemas

services/prompt_service.py
-> Prompt lifecycle and transaction orchestration

services/hook_service.py
-> Hook lifecycle and Revision transaction orchestration

services/compiler.py
-> pure parsing, caller-owned-cursor resolution, deterministic compilation

repositories/prompt_repository.py
-> explicit Prompt SQL

repositories/hook_repository.py
-> explicit Hook SQL and effective-Revision resolution

db.py
-> connections, transactions, migrations, startup, health
```

Historical root-level `compiler.py` and `hook_repository.py` remain inactive.
They use pre-v2 tables and are not imported into Phase 4A. Cleanup remains a
separate reviewable task unless removal can be proven safe and small.

## Prompt domain

Prompt rows store metadata only. Prompt text exists only in immutable Prompt
Revisions. Prompt Variants use `draft`, `available`, and `archived`.

Prompt Revision numbering is serialized by locking the Prompt and Variant rows
before allocating the next number.

## Hook domain

A Hook row stores stable metadata:

```text
hook_key
display_name
description
category
created_at
updated_at
deleted_at
```

A Hook Revision stores immutable content and behavior:

```text
revision_number
hook_group
hook_content
priority
is_enabled
change_note
created_at
```

Deleted Hooks retain their stable keys, cannot receive new Revisions, and do not
contribute to compilation. Permanent Hook deletion is not part of Phase 4A.

Hook groups are stored without `#` and match:

```text
hook_[A-Za-z0-9_.-]+
```

## Effective Hook Revision

The effective Hook Revision is always the Revision with the highest
`revision_number` for one Hook.

Consequences:

- a Hook without Revisions contributes nothing;
- only the latest Revision is considered;
- no fallback to an older enabled Revision occurs;
- a disabled latest Revision disables the contribution;
- a deleted Hook contributes nothing;
- restoration reuses the latest Revision and its enabled state.

## Hook Revision concurrency

Creation runs in one explicit transaction:

```text
SELECT Hook row FOR UPDATE
-> verify lifecycle state
-> calculate MAX(revision_number) + 1
-> insert immutable Revision
-> commit
```

The unique `(hook_id, revision_number)` constraint remains the final safety
boundary. No retry loop hides an incorrect locking design.

## Compiler

Placeholder grammar:

```text
#hook_[A-Za-z0-9_.-]+
```

The parser preserves first-occurrence group order and deduplicates detected
metadata. Resolution loads all requested groups through one repository query.

For each group, enabled effective Revisions are ordered by:

```text
priority ASC
hook_key ASC
```

Hook contents are joined using:

```text
\n\n
```

The compiler is transaction-compatible:

```text
parse placeholders
-> pure function

load effective Hook Revisions
-> caller-provided PostgreSQL cursor

compile resolved content
-> pure function
```

Preview mode preserves unresolved tokens and reports them. Strict mode fails
with `unresolved_hook_groups` and returns no successful partial result.

## Prompt Revision compiled preview

```http
GET /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions/
    {revision}/compiled-preview
```

This endpoint loads an exact immutable Prompt Revision and compiles it against
current effective Hook Revisions. It performs no writes.

The result is mutable when Hook state changes. It is not a published artifact,
final runtime API, Bundle endpoint, or n8n production contract.

## Current Hook API

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

Hook Revision `PATCH`, `PUT`, and `DELETE` do not exist.

## Errors

Stable Hook and compiler errors include:

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

Raw SQL, table names, PostgreSQL messages, connection details, stack traces,
and Prompt or Hook content are not exposed by default.

## Security

Browser writes validate exact local `Origin` or `Referer` hosts:

```text
localhost
127.0.0.1
::1
```

Malicious prefix and subdomain matches are rejected. All responses retain
`Cache-Control: no-cache`. Initial deployment remains local-only.

## UI scope

Active navigation remains:

```text
Dashboard
Prompts
Families
Deleted Records
FastAPI documentation
```

`/hooks` stays unregistered and returns a normal HTML `404` until Phase 4B.

## Database and migrations

The active baseline remains:

```text
database/migrations/005_prompt_model_v2.sql
```

Phase 4A uses the existing `ai_hooks` and `ai_hook_revisions` schema. No new
migration is expected. Fresh, repeated, and concurrent startup behavior must
remain unchanged.

## Validation baseline

Every pull request runs:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Phase 4A validation must cover:

- Hook metadata lifecycle and filters;
- immutable Hook Revision history;
- rollback and concurrent numbering;
- effective Revision selection without fallback;
- deterministic parser, ordering, and separator;
- preview and strict modes;
- Prompt Revision compiled preview;
- OpenAPI and absent mutation routes;
- Prompt API/UI regressions;
- exact-origin safeguards;
- fresh, repeated, and concurrent startup;
- Docker image build and `/healthz`.

Do not claim validation success until checks are executed successfully.

## Documentation

Phase 4A updates:

```text
README.md
docs/hook-domain-api.md
docs/hook-compiler.md
docs/prompt-admin-v2-plan.md
```

`UsingSession/localai` documentation remains unchanged because runtime Bundle
retrieval and n8n integration are not implemented in Phase 4A.

## Out of scope for Phase 4A

- Hook administration UI and active navigation;
- Hook Revision comparison and impact views;
- permanent Hook deletion;
- Bundles, Bundle Revisions, role mappings, and publication;
- Compiled Bundle Artifacts and hashes;
- final runtime Bundle retrieval and ETag;
- n8n integration and `localai` image changes;
- import/export;
- authentication, ORM, Alembic, or frontend frameworks;
- project-specific records or seed data.

## Definition of done

Prompt Admin v2 is complete only when Hooks compile deterministically, Bundles
publish immutable artifacts, runtime consumers retrieve complete published
Bundles, import/export is versioned, backups are verified, and released Docker
images are pinned in `localai`.
