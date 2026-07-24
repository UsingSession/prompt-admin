# Prompt Admin v2 Upgrade Plan

**Status:** accepted architecture and active implementation plan  
**Target repository:** `UsingSession/prompt-admin`  
**Related platform:** `UsingSession/localai`  
**Prepared:** 2026-07-22  
**Last updated:** 2026-07-24

## Implementation progress

### Phase 1 — FastAPI foundation

**Status:** completed and merged into `main`.

Implementation was delivered through `UsingSession/prompt-admin` PR #3,
`Add FastAPI foundation`.

Phase 1 replaced the Python standard-library HTTP server with FastAPI and
Uvicorn and established the application factory, lifespan startup, health
endpoint, common errors, static-file mounting, local-origin safeguards, and
GitHub Actions validation.

### Phase 2 — Prompt Admin v2 database schema

**Status:** completed and merged into `main` before Phase 3A.

The current `main` branch contains the clean Prompt Admin v2 PostgreSQL schema,
ordered SQL migrations, explicit `db.transaction()` support, schema-state
validation, advisory locking for concurrent startup, and schema and startup
tests. No pre-v2 data migration or compatibility path is implemented.

The schema foundation includes Prompt, Hook, Bundle, and Compiled Artifact
tables. The current application activates behavior for the Prompt domain and
Deleted Records lifecycle only.

### Phase 3A — Prompt domain API

**Status:** completed and merged into `main`.

Implementation was delivered through `UsingSession/prompt-admin` PR #5,
`Add Prompt Admin v2 prompt domain API`.

Verified repository state:

```text
final validated PR head: fbc2231dea1a5e99ae1f90445cf4ace919403ec3
merge commit:            4bd628cb20277da43521a8626b1f61f6ce7f5863
```

Phase 3A implemented:

- Prompt Family lifecycle management API;
- Prompt lifecycle management API;
- Prompt Variant management and lifecycle API;
- immutable Prompt Revision create, list, and read API;
- strict Pydantic schemas and stable-key validation;
- Prompt-domain service and repository layers;
- stable domain errors;
- concurrency-safe sequential Revision creation;
- PostgreSQL, FastAPI, validation, OpenAPI, and removed-route tests.

### Phase 3B — Prompt administration UI and Revision comparison

**Status:** completed and merged into `main`.

Implementation was delivered through `UsingSession/prompt-admin` PR #6,
`Add Prompt Admin v2 management UI`.

Verified repository state on 2026-07-24:

```text
final PR head:            a4816727bcff58b0c360e42a9dbfbe03d4bb9aa3
merge commit:             835a5a1ed47cd624579532dbad86a28c80fe5145
current main:              835a5a1ed47cd624579532dbad86a28c80fe5145
automated validation was recorded on: 4040eb3507b61a1df713b51358bafdb4416d2419
```

Phase 3B implemented:

- a server-rendered Jinja2 application shell and dashboard;
- active navigation for Dashboard, Prompts, Families, Deleted Records, and
  FastAPI documentation;
- Prompt Family list, create, detail, edit, soft-delete, and restore pages;
- Prompt list and filters, create, detail, edit, soft-delete, and restore pages;
- Prompt Variant create, detail, edit, status, and Revision-history pages;
- immutable Prompt Revision create, detail, and copy-as-new workflows;
- unified and side-by-side Prompt Revision comparison using `difflib`;
- HTML form validation through existing Pydantic schemas;
- Post/Redirect/Get with `303 See Other`;
- core administration without a JavaScript dependency;
- a Deleted Records basket for soft-deleted Families and Prompts;
- guarded permanent deletion and stable-key reuse after permanent deletion;
- protection against deleting Prompt Revisions referenced by Bundle items;
- unchanged `/api/v1` Prompt-domain management contract;
- UI route tests and real PostgreSQL UI lifecycle tests;
- README updates and `docs/prompt-management-ui.md`.

PR #6 reports successful automated validation for the complete Python unittest
suite, real PostgreSQL integration tests, Docker image build, concurrent startup
against empty PostgreSQL, and `/healthz` checks. The PR description stated that
manual desktop and narrow-viewport inspection was required; no separate
machine-readable inspection result was found in the repository evidence used
for this knowledge update.

The next implementation step is:

```text
Phase 4A — Hook domain backend, immutable Hook Revisions, and deterministic compiler
```

The Hook administration UI and impact views should remain a separate Phase 4B
unless repository inspection demonstrates that one combined PR remains small
and reviewable.


## 1. Purpose

Prompt Admin should become a generic prompt-management service for multiple
runtime consumers, including:

- n8n multi-step workflows;
- Claude CLI configurations;
- single-system-message chats;
- future local AI projects.

The most complex reference use case is image prompt generation:

```text
idea_generator
-> character_generator
-> tag_retrieval_planner
-> script_writer
```

Prompt Admin must provide the prompts used by these steps, but it must not own
the workflow sequence, model calls, Qdrant queries, retries, or data mapping
between steps.

## 2. Repository boundaries

### `UsingSession/prompt-admin` owns

- Prompt Admin application code;
- UI and HTTP API;
- prompt, hook, bundle, and revision domain logic;
- PostgreSQL schema and migrations;
- compilation and publication rules;
- tests;
- Dockerfile and application releases.

### `UsingSession/localai` owns

- Docker Compose orchestration;
- networking and port binding;
- PostgreSQL service configuration;
- Prompt Admin image version pinning;
- backups and restore tooling;
- integration documentation;
- n8n runtime wiring.

### Project-specific repositories own

- image-generation prompts;
- Danbooru retrieval rules;
- Qdrant collections and datasets;
- project-specific bundle definitions;
- project-specific n8n workflows.

## 3. Accepted decisions

The following decisions are accepted and should guide implementation.

1. Backward compatibility with the current Prompt Admin data model is not
   required.
2. Existing data may be exported before migration and recreated or imported
   manually afterward.
3. Prompt Admin remains a custom domain application rather than being rebuilt
   on a generic CMS.
4. The Python standard-library HTTP server has been replaced with FastAPI and
   Uvicorn.
5. The UI remains server-rendered with Jinja2, plain CSS, and limited vanilla
   JavaScript.
6. PostgreSQL access remains explicit through `psycopg` and SQL repositories.
7. An ORM and frontend framework are not required initially.
8. Prompt families remain human-facing logical groups, not revision chains and
   not runtime selectors.
9. A logical prompt, a variant, and a revision are separate concepts.
10. Prompt keys must not encode revisions through suffixes such as `_v1` or
    `_v2`.
11. Different input or output contracts are separate prompts, not variants.
12. Bundles are the primary runtime unit consumed by n8n, Claude CLI, and chat
    integrations.
13. Bundle revisions pin exact prompt revisions.
14. Prompt and hook revisions are immutable.
15. Publishing a bundle materializes a complete compiled runtime artifact.
16. Unresolved hooks or invalid references block publication.
17. Runtime consumers retrieve published compiled bundles through the Prompt
    Admin API and never query Prompt Admin tables directly.
18. Workflow ordering and workflow business logic remain in n8n child
    workflows.

## 4. Current implementation

Prompt Admin v2 currently includes the Phase 1 FastAPI foundation, the Phase 2
PostgreSQL schema foundation, the merged Phase 3A Prompt-domain management API,
and the merged Phase 3B server-rendered Prompt administration UI.

### Current HTTP and application foundation

- FastAPI application factory and Uvicorn runtime;
- lifespan startup for schema initialization and ordered SQL migrations;
- `GET /healthz`;
- Starlette static-file mounting;
- Jinja2 server-rendered administration pages and HTML error pages;
- Pydantic environment, API, and HTML form-boundary validation;
- machine-readable API error envelopes;
- local browser write-origin safeguards for `POST`, `PUT`, `PATCH`, and
  `DELETE`;
- `Cache-Control: no-cache`;
- GitHub Actions with PostgreSQL, unittest, Docker build, concurrent startup,
  and health validation.

### Current Prompt-domain architecture

API requests:

```text
FastAPI API route
-> Pydantic boundary schema
-> Prompt-domain service
-> explicit PostgreSQL repository
-> Prompt Admin v2 schema
```

Browser administration:

```text
Browser
-> FastAPI UI route
-> parse path, query, or URL-encoded form data
-> existing Pydantic schema
-> Prompt-domain or Deleted Records service
-> explicit PostgreSQL repository
-> Jinja2 response or 303 redirect
```

Active modules include:

```text
app.py
-> application creation, lifespan, middleware, static files, and exception handling

routes.py
-> Prompt management UI router registration
-> Deleted Records UI router registration
-> /api/v1 Prompt management router registration
-> GET /healthz

api/prompt_management.py
-> versioned /api/v1 FastAPI handlers

ui/prompt_management.py
-> dashboard, Families, Prompts, Variants, Revisions, and comparison pages

ui/deleted_records.py
-> Deleted Records basket and permanent-delete UI actions

schemas/prompt.py
-> strict API and HTML form-boundary schemas

services/prompt_service.py
-> Prompt lifecycle rules and transaction orchestration

services/deleted_record_service.py
-> permanent-deletion lifecycle and reference checks

repositories/prompt_repository.py
-> parameterized Prompt-domain psycopg SQL

repositories/deleted_record_repository.py
-> deleted-record queries and guarded permanent deletion

db.py
-> connection, transaction, migration, and health helpers
```

No ORM, Alembic, frontend framework, generic repository framework, or new
multipart/form dependency was introduced by Phase 3B.

### Current Prompt-domain behavior

Prompt Family:

- create, list, read, mutable metadata update, soft delete, and restore;
- immutable `family_key`;
- deleting a Family does not delete its Prompts;
- active, deleted, and combined list states are available in the UI.

Prompt:

- create, list, read, mutable metadata update, optional Family association,
  soft delete, and restore;
- immutable `prompt_key`;
- Prompt rows contain metadata only;
- deleted Prompts cannot receive new Variants or Revisions;
- list filtering supports Family, category, and lifecycle state.

Prompt Variant:

- create, list, read, mutable metadata and lifecycle status updates;
- immutable `variant_key` within one Prompt;
- statuses are `draft`, `available`, and `archived`;
- archived Variants retain history but cannot receive new Revisions;
- Variant deletion is not exposed; lifecycle retirement uses `archived`.

Prompt Revision:

- create, list, and read;
- immutable append-only history;
- exact Prompt text preservation;
- ascending deterministic history order;
- sequential numbering per Prompt Variant;
- no update or delete API, service, repository, or UI action;
- old content may be copied into a new-Revision form, but saving creates a new
  immutable Revision;
- unified and side-by-side same-Variant comparison is available.

### Current administration UI

Active navigation:

```text
Dashboard
Prompts
Families
Deleted Records
FastAPI documentation
```

The root route is the active dashboard:

```http
GET /
```

Families:

```http
GET  /families
GET  /families/new
POST /families
GET  /families/{family_key}
GET  /families/{family_key}/edit
POST /families/{family_key}/edit
POST /families/{family_key}/delete
POST /families/{family_key}/restore
```

Prompts:

```http
GET  /prompts
GET  /prompts/new
POST /prompts
GET  /prompts/{prompt_key}
GET  /prompts/{prompt_key}/edit
POST /prompts/{prompt_key}/edit
POST /prompts/{prompt_key}/delete
POST /prompts/{prompt_key}/restore
```

Deleted Records:

```http
GET  /deleted
POST /deleted/families/{family_key}/permanent-delete
POST /deleted/prompts/{prompt_key}/permanent-delete
```

Variants:

```http
GET  /prompts/{prompt_key}/variants/new
POST /prompts/{prompt_key}/variants
GET  /prompts/{prompt_key}/variants/{variant_key}
GET  /prompts/{prompt_key}/variants/{variant_key}/edit
POST /prompts/{prompt_key}/variants/{variant_key}/edit
```

Revisions:

```http
GET  /prompts/{prompt_key}/variants/{variant_key}/revisions/new
POST /prompts/{prompt_key}/variants/{variant_key}/revisions
GET  /prompts/{prompt_key}/variants/{variant_key}/revisions/{revision}
GET  /prompts/{prompt_key}/variants/{variant_key}/compare
```

The comparison route accepts `from_revision` and `to_revision` query
parameters. It compares only Revisions belonging to the route's Prompt Variant
and performs no writes.

UI mutations use normal HTML POST routes and Post/Redirect/Get with `303 See
Other`. Existing Pydantic schemas validate submitted values. Invalid forms
preserve safe submitted values and render field or summary errors.

Jinja2 autoescaping remains enabled. Prompt and diff text is never marked safe.
Core administration does not depend on JavaScript.

### Deleted Records lifecycle

Soft-deleted Families and Prompts remain in the Deleted Records basket. Their
stable keys remain reserved until permanent deletion.

Permanent deletion is available only after soft deletion:

- Family permanent deletion removes the Family and detaches associated Prompts
  through the existing foreign-key behavior;
- associated Prompts are not deleted with the Family;
- Prompt permanent deletion removes owned Variants and immutable Revisions;
- Prompt permanent deletion is blocked when any owned Revision is referenced by
  a Bundle item;
- successful permanent deletion releases the stable key for future reuse;
- duplicate active and deleted stable keys are not allowed.

### Current management API

The `/api/v1` Prompt-domain management contract remains unchanged by Phase 3B.

Families:

```http
GET    /api/v1/families
POST   /api/v1/families
GET    /api/v1/families/{family_key}
PATCH  /api/v1/families/{family_key}
DELETE /api/v1/families/{family_key}
POST   /api/v1/families/{family_key}/restore
```

Prompts:

```http
GET    /api/v1/prompts
POST   /api/v1/prompts
GET    /api/v1/prompts/{prompt_key}
PATCH  /api/v1/prompts/{prompt_key}
DELETE /api/v1/prompts/{prompt_key}
POST   /api/v1/prompts/{prompt_key}/restore
```

Variants:

```http
GET   /api/v1/prompts/{prompt_key}/variants
POST  /api/v1/prompts/{prompt_key}/variants
GET   /api/v1/prompts/{prompt_key}/variants/{variant_key}
PATCH /api/v1/prompts/{prompt_key}/variants/{variant_key}
```

Revisions:

```http
GET  /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions
POST /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions
GET  /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions/{revision}
```

### Transactions and concurrent Revision creation

Multi-check writes use `db.transaction()`. Successful operations commit after
the context exits. Failures roll back and close cursors and connections safely.
SQL remains explicit through `psycopg`.

Revision creation uses one transaction:

```text
lock Prompt row
-> verify Prompt state
-> lock Variant row with SELECT ... FOR UPDATE
-> verify Variant state
-> calculate MAX(revision_number) + 1
-> insert Revision
-> commit
```

The Variant row lock serializes concurrent Revision creation for one Variant.
The unique `(variant_id, revision_number)` constraint remains the final safety
boundary. No retry loop hides transaction-design errors.

### Stable keys, validation, and errors

`family_key`, `prompt_key`, and `variant_key` are immutable. Invalid keys are
rejected rather than normalized into different keys. Revision numbers are
stored separately and cannot be encoded using `_v1`, `_v2`, or similar stable-
key suffixes. Unsupported request fields are rejected. Prompt text is accepted
through Prompt Revision creation, not Prompt metadata creation or update.

Stable Prompt-domain error codes are:

```text
family_not_found
family_key_conflict
family_deleted
prompt_not_found
prompt_key_conflict
prompt_deleted
variant_not_found
variant_key_conflict
variant_archived
invalid_variant_status
revision_not_found
revision_conflict
invalid_reference
database_unavailable
```

Raw PostgreSQL errors, SQL statements, table names, connection details, and
stack traces are not exposed through documented API or UI responses.

### Current exclusions

Hooks, Hook Revisions, compilation, Bundles, publication, Compiled Artifacts,
the final Bundle runtime API, ETag support, and v2 import/export remain deferred
to later phases.

Pre-v2 routes such as `/delete`, `/api-docs`, `/api/prompts/compiled`, and
`/save` remain unregistered and return normal `404 Not Found` responses. The
root route `/` is now the active Phase 3B dashboard. HTTP `503` is reserved for
actual service or database unavailability.

The current application provides Prompt management API and UI contracts but no
final runtime Prompt retrieval API for n8n or other consumers.


## 5. Target architecture

```text
Prompt Family
└─ Prompt
   ├─ Variant
   │  ├─ Revision 1
   │  ├─ Revision 2
   │  └─ Revision 3
   └─ Variant
      └─ Revision 1

Hook
└─ Hook Revision

Prompt Bundle
└─ Bundle Revision
   ├─ role -> exact prompt revision
   ├─ role -> exact prompt revision
   └─ compiled immutable artifact
```

### Concept definitions

#### Prompt

A stable logical task and input/output contract.

Examples:

```text
image.idea_generator
image.character_generator
image.tag_retrieval_planner
image.script_writer.danbooru
image.script_writer.natural_language
claude.drupal.system
chat.english_tutor.system
```

#### Variant

An alternative implementation of the same prompt contract.

Examples:

```text
baseline
candidate
experimental
qdrant
```

#### Revision

An immutable snapshot of one variant.

Example:

```text
image.idea_generator@candidate:r3
```

#### Family

A UI and organizational group for related prompts.

Examples:

```text
image.generation
image.script_writers
claude.coding
education.tutors
```

#### Bundle

A stable runtime configuration that maps consumer roles to exact prompt
revisions.

Examples:

```text
image.danbooru.production
image.danbooru.candidate
image.natural_language.production
claude.drupal
chat.english_tutor
```

#### Compiled artifact

The immutable JSON payload produced when a bundle revision is published. It
contains the exact compiled prompts and metadata returned to runtime consumers.

## 6. Prompt Admin v2 PostgreSQL model

Phase 2 implemented this PostgreSQL schema through ordered SQL migrations.
Internal numeric IDs are used for relations. Stable keys remain unique
human-readable identifiers used by the management API and future UI.

The schema includes the Prompt, Hook, Bundle, and Compiled Artifact tables.
Phase 3A application services currently manage only Prompt Families, Prompts,
Prompt Variants, and Prompt Revisions. Later domain services remain deferred.

### `ai_prompt_families`

```text
id BIGSERIAL PRIMARY KEY
family_key TEXT UNIQUE NOT NULL
display_name TEXT NOT NULL
description TEXT NOT NULL DEFAULT ''
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
deleted_at TIMESTAMPTZ NULL
```

### `ai_prompts`

```text
id BIGSERIAL PRIMARY KEY
prompt_key TEXT UNIQUE NOT NULL
display_name TEXT NOT NULL
description TEXT NOT NULL DEFAULT ''
category TEXT NOT NULL DEFAULT ''
prompt_family_id BIGINT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
deleted_at TIMESTAMPTZ NULL
```

`description` is human-facing metadata and is not sent to an LLM.

### `ai_prompt_variants`

```text
id BIGSERIAL PRIMARY KEY
prompt_id BIGINT NOT NULL
variant_key TEXT NOT NULL
display_name TEXT NOT NULL
description TEXT NOT NULL DEFAULT ''
status TEXT NOT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
deleted_at TIMESTAMPTZ NULL
```

Required constraint:

```sql
UNIQUE (prompt_id, variant_key)
```

Allowed statuses:

```text
draft
available
archived
```

`production` is not a variant status. Production selection belongs to a
published bundle revision.

### `ai_prompt_revisions`

```text
id BIGSERIAL PRIMARY KEY
variant_id BIGINT NOT NULL
revision_number INTEGER NOT NULL
system_prompt TEXT NOT NULL
change_note TEXT NOT NULL DEFAULT ''
created_at TIMESTAMPTZ NOT NULL
```

Required constraint:

```sql
UNIQUE (variant_id, revision_number)
```

Rows are immutable after creation.

### `ai_hooks`

```text
id BIGSERIAL PRIMARY KEY
hook_key TEXT UNIQUE NOT NULL
display_name TEXT NOT NULL
description TEXT NOT NULL DEFAULT ''
category TEXT NOT NULL DEFAULT ''
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
deleted_at TIMESTAMPTZ NULL
```

### `ai_hook_revisions`

```text
id BIGSERIAL PRIMARY KEY
hook_id BIGINT NOT NULL
revision_number INTEGER NOT NULL
hook_group TEXT NOT NULL
hook_content TEXT NOT NULL
priority INTEGER NOT NULL DEFAULT 100
is_enabled BOOLEAN NOT NULL DEFAULT TRUE
change_note TEXT NOT NULL DEFAULT ''
created_at TIMESTAMPTZ NOT NULL
```

Required constraint:

```sql
UNIQUE (hook_id, revision_number)
```

Rows are immutable after creation.

### `ai_prompt_bundles`

```text
id BIGSERIAL PRIMARY KEY
bundle_key TEXT UNIQUE NOT NULL
display_name TEXT NOT NULL
description TEXT NOT NULL DEFAULT ''
category TEXT NOT NULL DEFAULT ''
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
deleted_at TIMESTAMPTZ NULL
```

### `ai_prompt_bundle_revisions`

```text
id BIGSERIAL PRIMARY KEY
bundle_id BIGINT NOT NULL
revision_number INTEGER NOT NULL
status TEXT NOT NULL
change_note TEXT NOT NULL DEFAULT ''
created_at TIMESTAMPTZ NOT NULL
published_at TIMESTAMPTZ NULL
```

Required constraint:

```sql
UNIQUE (bundle_id, revision_number)
```

Recommended statuses:

```text
draft
published
superseded
```

A published or superseded bundle revision is immutable.

### `ai_prompt_bundle_items`

```text
id BIGSERIAL PRIMARY KEY
bundle_revision_id BIGINT NOT NULL
role_key TEXT NOT NULL
prompt_revision_id BIGINT NOT NULL
position INTEGER NOT NULL DEFAULT 100
```

Required constraint:

```sql
UNIQUE (bundle_revision_id, role_key)
```

Each item pins one exact prompt revision.

### `ai_compiled_bundle_artifacts`

```text
id BIGSERIAL PRIMARY KEY
bundle_revision_id BIGINT UNIQUE NOT NULL
content_hash TEXT UNIQUE NOT NULL
compiled_payload JSONB NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

The artifact is created transactionally during publication.

## 7. Domain invariants

The service must enforce these invariants in application logic and database
constraints where practical.

1. `prompt_key`, `variant_key`, `hook_key`, `family_key`, `bundle_key`, and
   `role_key` are stable identifiers.
2. Prompt keys never contain revision suffixes generated by the application.
3. A prompt revision cannot be updated after creation.
4. A hook revision cannot be updated after creation.
5. A published bundle revision cannot be updated.
6. Every bundle role points to an existing prompt revision.
7. A role key is unique within one bundle revision.
8. A bundle cannot be published with zero items.
9. A bundle cannot be published with unresolved hooks.
10. A bundle cannot be published with deleted or otherwise invalid references.
11. Publication creates one compiled artifact and one deterministic content
    hash.
12. A runtime request returns only a published artifact.
13. Runtime requests never compile mutable records dynamically.
14. The service must never return a partial bundle.
15. A referenced immutable revision cannot be permanently deleted.

## 8. Hook compilation

Prompt text continues to use hook placeholders.

Recommended naming:

```text
#hook_global.response_rules
#hook_image.common_quality
#hook_image.danbooru_output
#hook_claude.coding_rules
```

The compiler should:

1. parse placeholders in first-occurrence order;
2. resolve enabled hook revisions for each group;
3. order hooks by `priority`, then stable hook key;
4. insert hook contents deterministically;
5. report all detected groups;
6. reject unresolved groups during publication;
7. return warnings during draft preview;
8. calculate the final artifact hash from all effective content.

### Publication strategy

At publication time:

```text
bundle draft
-> validate bundle items
-> load exact prompt revisions
-> resolve effective hook revisions
-> compile every prompt
-> validate compiled output
-> build JSON artifact
-> calculate SHA-256 hash
-> store artifact
-> mark bundle revision published
```

The entire operation must run inside one PostgreSQL transaction.

## 9. Bundle examples

### Danbooru image generation

```text
Bundle: image.danbooru.production

idea_generator
-> image.idea_generator@baseline:r4

character_generator
-> image.character_generator@baseline:r2

tag_retrieval_planner
-> image.tag_retrieval_planner@qdrant:r7

script_writer
-> image.script_writer.danbooru@baseline:r5
```

### Natural-language image generation

```text
Bundle: image.natural_language.production

idea_generator
-> image.idea_generator@baseline:r4

character_generator
-> image.character_generator@baseline:r2

tag_retrieval_planner
-> image.tag_retrieval_planner@qdrant:r7

script_writer
-> image.script_writer.natural_language@baseline:r3
```

### Claude CLI

```text
Bundle: claude.drupal

system
-> claude.drupal.system@baseline:r6
```

### English tutor chat

```text
Bundle: chat.english_tutor

system
-> chat.english_tutor.system@baseline:r2
```

## 10. Runtime API

### Current runtime state

Phase 3B does not implement a final runtime Prompt retrieval endpoint.

Pre-v2 routes are no longer registered. In particular:

```http
GET /api/prompts/compiled
```

returns the normal API `404 Not Found` response. It is not available,
transitional, deprecated, or temporarily disabled. There is no compatibility
handler and no `legacy_domain_unavailable` response.

The implemented `/api/v1` routes are administration and management operations
for Prompt Families, Prompts, Prompt Variants, and Prompt Revisions. They are
not a substitute for the future published Bundle runtime contract.

Runtime consumers must not query Prompt Admin PostgreSQL tables directly. n8n
migration remains pending until Bundle publication and the runtime API are
implemented.

### Target primary endpoint

```http
GET /api/v1/bundles/{bundle_key}/compiled
```

This endpoint is target architecture only and is not implemented in Phase 3B.

Example target response:

```json
{
  "bundle_key": "image.danbooru.production",
  "revision": 8,
  "content_hash": "sha256:example",
  "published_at": "2026-07-22T10:00:00+00:00",
  "prompts": {
    "idea_generator": {
      "prompt_key": "image.idea_generator",
      "variant_key": "baseline",
      "revision": 4,
      "compiled_prompt": "..."
    },
    "script_writer": {
      "prompt_key": "image.script_writer.danbooru",
      "variant_key": "baseline",
      "revision": 5,
      "compiled_prompt": "..."
    }
  }
}
```

`prompts` should be a JSON object keyed by `role_key`. This lets n8n access a
Prompt without an additional mapping node:

```javascript
$json.prompts.script_writer.compiled_prompt
```

### Target historical artifact endpoint

```http
GET /api/v1/bundles/{bundle_key}/revisions/{revision}/compiled
```

This target endpoint supports debugging and reproducibility after Bundle
publication is implemented.

### Target Bundle metadata endpoints

```http
GET /api/v1/bundles/{bundle_key}
GET /api/v1/bundles/{bundle_key}/revisions
```

These Bundle endpoints are not implemented in Phase 3B. The current exact
Prompt-domain management routes are recorded in Section 4.

### Target HTTP behavior

Recommended statuses:

```text
200 successful read
400 malformed request
404 resource not found
409 invalid state transition or broken reference
422 compilation or validation failure
500 unexpected server error
503 database unavailable
```

Runtime endpoints should return stable machine-readable error codes.

### Target caching

Compiled responses should include:

```text
ETag: <content_hash>
```

Support:

```text
If-None-Match
-> 304 Not Modified
```

## 11. UI plan

### Current Phase 3B navigation

```text
Dashboard
Prompts
Families
Deleted Records
FastAPI documentation
```

Only implemented features are active navigation items. Hooks, Bundles,
import/export, and runtime artifacts are not presented as working pages.

### Current Prompt-domain pages

The Phase 3B UI currently provides:

- a dashboard with Prompt and Family summary information;
- Family active, deleted, and combined lists;
- Family create, detail, edit, soft-delete, restore, and associated-Prompt
  views;
- Prompt deterministic list with Family, category, and lifecycle filters;
- Prompt create, detail, edit, soft-delete, restore, and Variant views;
- Variant create, detail, edit, status, and deterministic Revision history;
- immutable Revision create and detail pages;
- optional copy of old Revision content into the create form;
- unified and side-by-side same-Variant Revision comparison;
- a Deleted Records basket with restore and guarded permanent deletion.

Core administration works without JavaScript. Mutations use normal POST forms
and Post/Redirect/Get.

### Current Revision comparison

```http
GET /prompts/{prompt_key}/variants/{variant_key}/compare
    ?from_revision=2
    &to_revision=5
```

The current implementation uses `difflib` and provides:

- explicit old and new Revision selection;
- Revision metadata and detail links;
- unified diff;
- side-by-side rows;
- line numbers;
- preserved whitespace;
- escaped Prompt and diff text;
- an empty state when fewer than two Revisions exist.

### Future Hook page

```text
Overview
Revisions
Hook groups
Used by prompts
Affected bundles
Compiled impact
```

### Future Bundle page

```text
Overview
Draft revision
Published revisions
Role mappings
Compiled preview
Validation issues
```

Future actions:

```text
Create draft revision
Clone published revision
Replace prompt revision
Validate
Compare revisions
Publish
Rollback by republishing an older mapping as a new revision
```

### Future comparison extensions

Later phases should extend comparison to:

- Hook Revisions;
- compiled Prompt output;
- Bundle role mappings;
- Compiled Bundle Artifacts.


## 12. Application stack

### Current Phase 3B stack

```text
fastapi
uvicorn
jinja2
pydantic
psycopg
Python difflib
plain CSS
minimal vanilla JavaScript enhancements
```

Current responsibilities:

```text
FastAPI
-> application factory
-> API and UI routing
-> OpenAPI for API routes
-> middleware and exception handling
-> static-file mounting

Uvicorn
-> ASGI process runtime

Jinja2
-> active server-rendered Prompt-domain administration pages
-> template inheritance through base.html
-> HTML error pages
-> autoescaped Prompt and diff content

Pydantic
-> environment configuration
-> strict Prompt-domain API schemas
-> HTML form-boundary validation

Prompt-domain services
-> lifecycle rules
-> transaction orchestration
-> stable domain error mapping

Deleted Records service
-> permanent-deletion lifecycle checks
-> reference protection

psycopg repositories
-> explicit parameterized PostgreSQL access
-> deterministic row mapping and ordering

Python difflib
-> read-only unified and side-by-side Prompt Revision comparison

SQL migrations
-> Prompt Admin v2 schema initialization and evolution
```

The UI uses standard URL-encoded form parsing and does not add a multipart
form dependency. Core operations do not depend on JavaScript.

### Target v2 responsibilities

```text
FastAPI
-> routing, request parsing, validation, OpenAPI, HTTP responses

Jinja2
-> all server-rendered administration UI pages

Pydantic
-> API, configuration, and form-boundary schemas

psycopg
-> explicit PostgreSQL transactions and repositories

SQL migrations
-> schema evolution
```

Not required initially:

```text
SQLAlchemy
Alembic
React
Vue
generic CMS
background worker
message queue
```


## 13. Application structure

### Current Phase 3B active structure

```text
prompt-admin/
├─ app.py
├─ routes.py
├─ config.py
├─ db.py
├─ errors.py
├─ api/
│  ├─ __init__.py
│  └─ prompt_management.py
├─ ui/
│  ├─ __init__.py
│  ├─ prompt_management.py
│  └─ deleted_records.py
├─ schemas/
│  ├─ __init__.py
│  └─ prompt.py
├─ services/
│  ├─ __init__.py
│  ├─ prompt_service.py
│  └─ deleted_record_service.py
├─ repositories/
│  ├─ prompt_repository.py
│  └─ deleted_record_repository.py
├─ database/
│  ├─ schema.sql
│  └─ migrations/
│     └─ 005_prompt_model_v2.sql
├─ docs/
│  ├─ prompt-domain-api.md
│  └─ prompt-management-ui.md
├─ templates/
│  ├─ base.html
│  ├─ dashboard.html
│  ├─ http_error.html
│  ├─ deleted/
│  │  └─ list.html
│  ├─ families/
│  │  ├─ list.html
│  │  ├─ detail.html
│  │  └─ form.html
│  ├─ prompts/
│  │  ├─ list.html
│  │  ├─ detail.html
│  │  └─ form.html
│  ├─ variants/
│  │  ├─ detail.html
│  │  └─ form.html
│  └─ revisions/
│     ├─ detail.html
│     ├─ form.html
│     └─ compare.html
├─ static/
│  └─ prompt-management.css
└─ tests/
   ├─ test_prompt_admin_fastapi.py
   ├─ test_prompt_domain_api.py
   ├─ test_prompt_domain_postgres.py
   ├─ test_prompt_domain_validation.py
   ├─ test_prompt_management_ui.py
   ├─ test_prompt_management_ui_postgres.py
   ├─ test_deleted_records_ui.py
   └─ test_deleted_records_postgres.py
```

This is the active Phase 3B path, not a claim that no other historical file
exists in the repository.

`app.py` remains limited to application creation, lifespan wiring, common
middleware, static files, and exception handling. `routes.py` registers the
Prompt management UI, Deleted Records UI, `/api/v1` Prompt management router,
and `/healthz`.

UI handlers call services directly and do not issue loopback HTTP requests or
execute SQL. The API contract remains owned by `api/prompt_management.py`.

### Target v2 structure

```text
prompt-admin/
├─ app.py
├─ config.py
├─ db.py
├─ domain/
│  ├─ prompts.py
│  ├─ hooks.py
│  ├─ bundles.py
│  └─ publishing.py
├─ repositories/
│  ├─ prompt_repository.py
│  ├─ hook_repository.py
│  ├─ bundle_repository.py
│  └─ artifact_repository.py
├─ services/
│  ├─ prompt_service.py
│  ├─ hook_service.py
│  ├─ compiler.py
│  └─ bundle_publisher.py
├─ api/
│  ├─ prompts.py
│  ├─ hooks.py
│  ├─ bundles.py
│  └─ health.py
├─ ui/
│  ├─ prompts.py
│  ├─ hooks.py
│  ├─ bundles.py
│  └─ families.py
├─ schemas/
├─ templates/
├─ static/
├─ database/
│  ├─ schema.sql
│  └─ migrations/
└─ tests/
```

The target structure should be introduced incrementally through small,
reviewable changes. `app.py` must remain limited to application creation,
dependency wiring, common application policy, and router registration.


## 14. Migration status

Backward compatibility with pre-v2 data and HTTP contracts is intentionally not
implemented.

Phase 2 completed the destructive schema transition after the PostgreSQL
database had been intentionally cleared. No automatic conversion, compatibility
view, or `_vN` key interpretation was added.

Current startup behavior is:

```text
database/schema.sql
-> create prompt_admin_migrations when absent
-> acquire PostgreSQL advisory transaction lock
-> apply unapplied SQL migrations in filename order
-> validate migration metadata against required v2 tables
-> commit
```

The active v2 baseline migration is:

```text
database/migrations/005_prompt_model_v2.sql
```

Repeated startup is idempotent. Concurrent startup is serialized by the
migration advisory lock. An incomplete schema whose tables and migration
metadata disagree is rejected rather than guessed or repaired automatically.

No pre-v2 records were migrated into the Phase 3A Prompt-domain API. Future v2
import/export support remains Phase 7 work.

## 15. Import and export v2

The export format should be versioned.

```json
{
  "schema_version": 2,
  "exported_at": "2026-07-22T10:00:00+00:00",
  "families": [],
  "prompts": [],
  "variants": [],
  "prompt_revisions": [],
  "hooks": [],
  "hook_revisions": [],
  "bundles": [],
  "bundle_revisions": [],
  "bundle_items": [],
  "compiled_artifacts": []
}
```

Import must support:

```text
parse
-> validate
-> show dry-run plan
-> apply transactionally
```

The import process must reject broken references and duplicate stable keys.

## 16. Implementation phases

Each phase should be a small reviewable PR based on the latest `main` branch.

### Phase 0 — Safety and design baseline

**Status:** completed as the accepted architecture baseline.

Deliverables:

- export and backup decisions;
- architecture documentation;
- accepted domain terminology;
- v2 API examples;
- stable naming rules.

### Phase 1 — FastAPI foundation — completed

Merged deliverables:

- FastAPI application factory and Uvicorn entrypoint;
- lifespan startup and health endpoint;
- framework-level Jinja2 errors and static-file mounting;
- Pydantic configuration validation;
- common API and UI errors;
- browser-origin safeguards and `Cache-Control: no-cache`;
- Dockerfile runtime update and GitHub Actions foundation;
- removal of the standard-library HTTP server and manual static handler.

Phase 1 history does not define the current route contract. Pre-v2 routes were
removed by the v2 schema and Prompt-domain implementation work.

### Phase 2 — v2 database schema — completed

Merged deliverables:

- clean Prompt Admin v2 schema and migration metadata;
- `005_prompt_model_v2.sql` with Prompt, Hook, Bundle, and Compiled Artifact
  tables and constraints;
- explicit `db.transaction()` helper;
- migration advisory locking and schema-state validation;
- schema, rollback, empty-database, idempotent-startup, and concurrent-startup
  tests.

### Phase 3A — Prompt domain API — completed

Merged through PR #5, `Add Prompt Admin v2 prompt domain API`.

Delivered:

- Prompt Family lifecycle management API;
- Prompt lifecycle management API;
- Prompt Variant management and lifecycle API;
- immutable Prompt Revision create, list, and read API;
- strict Pydantic schemas and stable-key validation;
- Prompt-domain service layer;
- expanded explicit PostgreSQL repository;
- stable domain errors;
- concurrency-safe sequential Revision creation;
- PostgreSQL, FastAPI, validation, OpenAPI, and removed-route tests;
- Prompt-domain README and API documentation.

### Phase 3B — Prompt administration UI and Revision comparison — completed

Merged through PR #6, `Add Prompt Admin v2 management UI`.

Delivered:

- server-rendered Prompt Admin application shell and dashboard;
- active navigation for implemented Prompt-domain features;
- Prompt Family create, list, detail, edit, soft-delete, and restore pages;
- Prompt create, list, filters, detail, edit, soft-delete, and restore pages;
- Prompt Variant create, detail, edit, and lifecycle pages;
- immutable Prompt Revision create, detail, history, and copy-as-new workflow;
- unified and side-by-side Prompt Revision comparison;
- Pydantic-backed HTML validation and preserved form values;
- Post/Redirect/Get with `303 See Other`;
- JavaScript-independent core management;
- Deleted Records basket;
- guarded permanent deletion and stable-key reuse;
- referenced Prompt Revision protection during permanent Prompt deletion;
- UI route and real PostgreSQL lifecycle tests;
- Prompt management UI documentation.

### Phase 4 — Hooks and compiler — pending

Deliverables:

- Hook CRUD;
- immutable Hook Revisions;
- deterministic group resolution;
- strict and preview compilation modes;
- unresolved-Hook reporting;
- Hook impact view;
- compiler unit tests.

### Phase 5 — Bundles and publication — pending

Deliverables:

- Prompt Bundle CRUD;
- draft Bundle Revisions;
- role mappings;
- exact Prompt Revision pinning;
- Bundle validation;
- transactional publication;
- materialized Compiled Artifact and SHA-256 hash;
- rollback workflow;
- publication tests.

### Phase 6 — Runtime API — pending

Deliverables:

- compiled Bundle endpoint;
- historical Revision endpoint;
- stable runtime error codes;
- ETag and `If-None-Match` support;
- API documentation;
- n8n integration examples;
- contract tests.

### Phase 7 — Import, export, and administration UX — pending

Deliverables:

- v2 export;
- dry-run import;
- transactional import;
- deleted-record administration enhancements;
- additional filters and search;
- additional impact views;
- integration tests.

### Phase 8 — Release and integration — pending

Deliverables:

- release notes;
- versioned Docker image;
- `localai` image version update;
- n8n workflow migration to Bundle endpoints;
- smoke test from n8n;
- backup and restore verification;
- final documentation update.

## 17. Testing requirements

### Current Phase 3B validation baseline

Every pull request runs:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

PR #6 reports successful automated validation for:

```text
complete Python unittest suite
real PostgreSQL integration tests
Docker image build
concurrent startup against empty PostgreSQL
GET /healthz for both application containers
separate Docker build workflow
```

The validation record named commit
`4040eb3507b61a1df713b51358bafdb4416d2419`. PR #6 was later merged from final
head `a4816727bcff58b0c360e42a9dbfbe03d4bb9aa3` into merge commit
`835a5a1ed47cd624579532dbad86a28c80fe5145`.

Current verified coverage includes:

- healthy and degraded health responses;
- framework API and HTML error behavior;
- static-file mounting and lifespan database initialization;
- exact local-origin acceptance and malicious localhost-prefix rejection on API
  and UI writes;
- `Cache-Control: no-cache`;
- fresh schema initialization, migration metadata, idempotent startup, and
  concurrent startup;
- stable-key validation without silent normalization;
- strict Pydantic API and HTML form-boundary validation;
- unchanged `/api/v1` Prompt-domain route registration and OpenAPI paths;
- application shell, dashboard, active navigation, and static assets;
- Family list, create, detail, update, soft delete, restore, and associated
  Prompt presentation;
- Prompt list filters, create, detail, update, soft delete, and restore;
- Prompt Variant creation, detail, update, and lifecycle status presentation;
- immutable Prompt Revision creation, exact text rendering, deterministic
  history, and no mutation routes;
- archived Variant restrictions;
- Post/Redirect/Get behavior and HTML validation with preserved values;
- Jinja2 escaping of Prompt and diff content;
- unified and side-by-side same-Variant Revision comparison;
- comparison read-only behavior;
- Deleted Records list, restore, and permanent deletion;
- stable-key reuse after permanent deletion;
- Family permanent deletion without deleting associated Prompts;
- Prompt permanent deletion of owned Variants and Revisions;
- blocking permanent Prompt deletion when a Revision is referenced by a Bundle
  item;
- real PostgreSQL UI lifecycle flows;
- Docker image build and concurrent Docker health checks.

The PR description stated that manual desktop and narrow-viewport inspection
remained required. No separate machine-readable inspection result was found in
the repository evidence used for this knowledge update.

The following subsections retain target coverage for later v2 phases.

### Unit tests

- Hook stable-key and Revision validation;
- Hook placeholder parsing;
- Hook ordering;
- unresolved Hook detection;
- deterministic compilation;
- content hash calculation;
- Bundle validation;
- publication state transitions.

### Repository tests

- Hook foreign-key and unique constraints;
- immutable Hook Revision behavior;
- transaction rollback;
- prevention of deleting referenced immutable Revisions;
- published Bundle immutability.

### API tests

- Hook management API;
- successful Bundle retrieval;
- unknown Bundle;
- unpublished Bundle;
- historical artifact retrieval;
- ETag behavior;
- runtime error response structure;
- no partial responses.

### UI tests

Current Prompt-domain UI coverage is implemented. Later phases require:

- create Hook and Hook Revision;
- preview unresolved Hooks;
- inspect Hook impact;
- create Bundle draft;
- validate and publish Bundle;
- inspect Compiled Artifact;
- clone published mapping into a new draft.

### Integration tests

- Hook compiler integration;
- Bundle publication transaction;
- n8n retrieval of a published Bundle;
- restore from PostgreSQL backup;
- import and export round trip.


## 18. Security and operational requirements

Initial deployment remains local-only.

### Current Phase 3B controls

Prompt Admin must be bound to `127.0.0.1` through `localai`.

Browser write requests using `POST`, `PUT`, `PATCH`, or `DELETE` validate
`Origin` when available and otherwise validate `Referer`.

Accepted browser hosts are exact matches:

```text
localhost
127.0.0.1
::1
```

HTTP and HTTPS are supported.

Prefix matches such as the following must be rejected:

```text
localhost.example.com
localhost.evil.example
```

Requests without `Origin` or `Referer` remain supported for local command-line
and service clients.

All responses include:

```text
Cache-Control: no-cache
```

Configuration validation must preserve secrets exactly. In particular,
`POSTGRES_PASSWORD` must not be stripped or normalized.

Generic `500` responses are returned to clients while diagnostic information is
logged locally.

### Required controls for all phases

- do not expose Adminer or Prompt Admin publicly;
- validate all stable keys and form inputs;
- use parameterized SQL;
- use explicit transactions for publication and import;
- do not log prompt contents by default;
- do not place secrets in exported prompt data;
- include Prompt Admin tables in PostgreSQL backups;
- pin released Docker image versions.

Authentication is not required for the initial local-only deployment. Origin
validation is defense in depth and is not a replacement for authentication.
Authentication must be reconsidered before any LAN or public exposure.

## 19. Target n8n integration contract

This contract is target architecture and is not implemented in Phase 3B. The
current application has Prompt management API and UI contracts but no final
runtime Prompt retrieval endpoint, and n8n integration changes remain deferred.

After Bundle publication and the runtime API are implemented, n8n child
workflows should retrieve one Prompt Bundle by stable key.

Target request:

```text
GET http://prompt-admin:8090/api/v1/bundles/
    image.danbooru.production/compiled
```

Expected usage:

```javascript
const ideaPrompt = $json.prompts.idea_generator.compiled_prompt;
const scriptPrompt = $json.prompts.script_writer.compiled_prompt;
```

n8n remains responsible for:

- execution order;
- model selection;
- input and output mapping;
- Qdrant retrieval;
- retries;
- failure routing;
- workflow-specific configuration.

Prompt Admin remains responsible for:

- prompt identities;
- variants and revisions;
- hooks and compilation;
- bundle mappings;
- publication;
- immutable runtime artifacts.

## 20. Non-goals

Prompt Admin v2 should not:

- become a workflow builder;
- store n8n node graphs;
- execute model calls;
- query Qdrant;
- own Danbooru datasets;
- contain project-specific starter prompts;
- select models dynamically;
- replace project-specific workflow repositories;
- expose its internal PostgreSQL tables as a public contract;
- add a frontend framework without a concrete requirement;
- add a generic CMS abstraction.

## 21. Remaining implementation choices

These choices may be resolved during detailed design without changing the
accepted architecture.

### Category storage

Recommended initial choice:

```text
free text field
```

A category table can be introduced later if referential management becomes
necessary.

### Soft deletion of immutable revisions

Recommended choice:

- immutable revisions are not soft-deleted individually;
- definitions and variants may be archived;
- referenced revisions cannot be permanently deleted.

### Bundle item ordering

Recommended choice:

- preserve a `position` field for UI and deterministic export;
- runtime access continues to use `role_key`.

### Current published bundle pointer

Recommended choice:

- determine the current publication from the latest published bundle revision;
- optionally add an explicit pointer only if concurrent publication performance
  or locking requires it.

## 22. Definition of done

Prompt Admin v2 as a whole is not complete after Phase 3B.

Current progress:

- the fresh v2 schema and migration foundation are complete;
- Prompt stable-key validation is complete;
- Prompt Family, Prompt, and Prompt Variant management APIs are complete;
- immutable Prompt Revision creation and history are complete;
- concurrent sequential Revision numbering is complete;
- server-rendered Prompt administration pages are complete;
- Prompt Revision unified and side-by-side comparison is complete;
- soft-delete, restore, Deleted Records, and guarded permanent deletion flows
  are complete for Families and Prompts;
- Hooks, Bundles, publication, runtime retrieval, import/export, release, and
  `localai` integration remain pending.

Prompt Admin v2 is complete only when:

1. a fresh database starts with only schema and migration metadata;
2. Prompts use stable keys without `_vN` Revision suffixes;
3. Prompt Variants and immutable Prompt Revisions can be created and compared;
4. Hooks have immutable Hook Revisions and deterministic compilation;
5. Prompt Bundles pin exact Prompt Revisions by role;
6. invalid Bundles cannot be published;
7. publication creates an immutable Compiled Artifact and content hash;
8. n8n can retrieve a complete Prompt Bundle through one API request;
9. runtime responses are reproducible by Bundle Revision and hash;
10. import and export use schema version 2;
11. backup and restore are verified;
12. tests cover domain, repository, compiler, API, UI, and integration behavior;
13. `prompt-admin` and `localai` documentation reflect the final contract;
14. a versioned Prompt Admin Docker image is released and pinned in `localai`.


## 23. Documentation updates after implementation

Phase 3A updated `README.md` and added `docs/prompt-domain-api.md` with the
Prompt-domain API contract, lifecycle rules, errors, concurrency strategy, and
deferred work.

Phase 3B updated `README.md` and added `docs/prompt-management-ui.md` with:

- UI architecture and route contract;
- active navigation;
- Family, Prompt, Variant, and immutable Revision workflows;
- Post/Redirect/Get form handling;
- unified and side-by-side Revision comparison;
- Jinja2 escaping and local-origin safeguards;
- Deleted Records behavior;
- guarded permanent deletion and reference protection;
- UI and PostgreSQL integration testing guidance.

The remaining documentation items below apply to later phases.

### `UsingSession/prompt-admin`

Update as later phases land:

- Hook and compiler documentation;
- Bundle and publication architecture;
- runtime API documentation;
- database schema reference when migrations change;
- import and export format;
- release procedure;
- migration notes;
- testing instructions.

### `UsingSession/localai`

Update after runtime publication is implemented:

- Prompt Admin runtime endpoint;
- Bundle retrieval convention;
- pinned Prompt Admin image version;
- backup and restore documentation;
- n8n integration examples.

### Project knowledge base

Current knowledge records:

- accepted Prompt-domain terminology;
- stable naming conventions;
- Prompt management API and UI contracts;
- immutable Prompt Revision behavior;
- Deleted Records and permanent-deletion safeguards;
- repository ownership boundaries.

Later updates must record:

- Hook and compiler contracts;
- Bundle keys and role keys;
- publication workflow;
- final runtime API response contract.
