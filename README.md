# Prompt Admin

Prompt Admin is a local, generic prompt-management service backed by
PostgreSQL. It owns prompt-management application logic, UI and API behavior,
database migrations, tests, Docker image construction, and releases.

Prompt Admin does not own workflow graphs, model calls, Qdrant datasets,
project-specific prompts, or `UsingSession/localai` orchestration.

## Current implementation

Prompt Admin v2 Phase 3B provides:

- FastAPI application factory and Uvicorn runtime;
- lifespan-based PostgreSQL initialization;
- a clean v2 database schema;
- explicit `psycopg` SQL and transaction helpers;
- versioned Prompt-domain management API;
- server-rendered Prompt management UI;
- Prompt Family create, read, update, soft delete, and restore workflows;
- Prompt metadata create, read, update, soft delete, and restore workflows;
- Prompt Variant create, read, update, and lifecycle status workflows;
- immutable Prompt Revision creation, history, detail, and comparison;
- unified and side-by-side Revision diffs;
- concurrency-safe Revision numbering;
- stable domain error codes;
- Pydantic API and HTML form-boundary validation;
- real PostgreSQL domain and UI integration tests;
- Docker startup and health smoke tests.

Hooks, Bundles, publication, compiled artifacts, the final runtime Bundle API,
and import/export remain deferred.

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
repository and do not expose it publicly without authentication and deployment
controls.

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

The Docker image uses the same application factory entrypoint.

## Prompt domain

```text
Prompt Family
└─ Prompt
   └─ Prompt Variant
      ├─ Prompt Revision 1
      └─ Prompt Revision 2
```

- A Family is optional organizational metadata.
- A Prompt is a stable logical task and input/output contract.
- A Variant is an alternative implementation of the same contract.
- A Revision is an immutable prompt-text snapshot.

Prompt text exists only in `ai_prompt_revisions`. Prompt rows contain metadata
only.

Variant statuses are:

```text
draft
available
archived
```

`production` is not a Variant status. Production selection belongs to a future
published Bundle Revision.

Detailed domain and API behavior:

```text
docs/prompt-domain-api.md
docs/prompt-management-ui.md
```

## Server-rendered UI

The UI uses:

```text
FastAPI UI route
-> parse path, query, or URL-encoded form data
-> construct existing Pydantic command schema
-> call Prompt-domain service
-> render Jinja2 or return 303 redirect
```

The UI does not call `/api/v1` over HTTP and does not execute SQL. API and UI
handlers use the same Prompt-domain service layer.

Core management works without JavaScript. HTML mutations use Post/Redirect/Get.

Active navigation is intentionally limited to:

```text
Dashboard
Prompts
Families
FastAPI documentation
```

Hooks, Bundles, import/export, and runtime artifacts are not presented as active
features before their implementation phases.

### UI routes

Dashboard:

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

The compare route accepts:

```text
?from_revision=2&to_revision=5
```

Only Revisions under the Prompt Variant identified by the route are loaded.

## Management API

The versioned `/api/v1` Prompt-domain management API remains unchanged by the
UI implementation.

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

Variants and Revisions:

```http
GET   /api/v1/prompts/{prompt_key}/variants
POST  /api/v1/prompts/{prompt_key}/variants
GET   /api/v1/prompts/{prompt_key}/variants/{variant_key}
PATCH /api/v1/prompts/{prompt_key}/variants/{variant_key}

GET  /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions
POST /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions
GET  /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions/{revision}
```

Prompt Revisions expose no update or delete route.

## Lifecycle behavior

Families and Prompts use soft deletion and explicit restoration. Deleted
records are displayed as deleted and are never presented as active.

Deleting a Family does not delete its associated Prompts.

Variants use `draft`, `available`, and `archived`. Variant deletion is not
implemented. Archived Variants retain immutable Revision history but reject new
Revision creation.

Prompt Revisions are immutable. Existing Revision pages provide no edit or
delete controls. An old Revision may be copied into the create form, but saving
always creates a new Revision.

## Revision comparison

Revision comparison uses Python `difflib` and performs no writes.

The page provides:

- explicit old and new Revision selection;
- old and new metadata;
- unified diff;
- side-by-side diff;
- line numbers;
- whitespace-preserving Prompt text;
- links to both Revision detail pages;
- an empty state when fewer than two Revisions exist.

Jinja2 autoescaping remains enabled. Prompt and diff content is never inserted
as trusted HTML.

## Stable keys

`family_key`, `prompt_key`, and `variant_key` are immutable after creation.

The application rejects:

- empty or whitespace-only keys;
- surrounding whitespace;
- keys longer than 120 characters;
- revision suffixes such as `_v1` and `_v2`.

Invalid keys are not silently normalized.

## Security

Browser writes using `POST`, `PUT`, `PATCH`, or `DELETE` validate `Origin` when
present and otherwise validate `Referer`.

Accepted browser hosts are exact matches:

```text
localhost
127.0.0.1
::1
```

Malicious prefix or subdomain values such as `localhost.evil.example` are
rejected. Requests without either header remain supported for local non-browser
clients.

All responses retain:

```text
Cache-Control: no-cache
```

Prompt text is not logged by UI handlers. Raw SQL or PostgreSQL exception
details are not rendered.

## Database initialization

The PostgreSQL database was intentionally reset before Phase 2. No legacy data
migration, conversion, or compatibility path is implemented.

Startup runs:

```text
database/schema.sql
-> creates prompt_admin_migrations only
-> applies unapplied SQL files from database/migrations in filename order
```

The v2 baseline migration is:

```text
database/migrations/005_prompt_model_v2.sql
```

Repeated startup is idempotent. Startup acquires a PostgreSQL advisory
transaction lock and validates migration metadata against the expected v2
tables.

Recovery and schema details:

```text
docs/v2-database-recovery.md
docs/v2-database-schema.md
```

## Tests

Install development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the complete suite against a dedicated PostgreSQL database:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Coverage includes:

- application shell and active navigation;
- HTML form validation and preserved values;
- Post/Redirect/Get behavior;
- Family, Prompt, and Variant management pages;
- soft delete and restore presentation;
- immutable Revision creation and detail;
- archived Variant restrictions;
- unified and side-by-side comparison;
- escaped Prompt and diff content;
- comparison read-only behavior;
- unchanged `/api/v1` OpenAPI routes;
- exact local-origin safeguards;
- real PostgreSQL UI lifecycle flows;
- fresh and repeated database startup;
- Docker image build and `/healthz`.

## Removed pre-v2 routes

Backward compatibility with the pre-v2 domain is intentionally not provided.

Removed examples include:

```http
GET  /api-docs
GET  /api/prompts/compiled
POST /save
POST /delete
```

The root path is now the v2 administration dashboard. Other removed routes
remain unregistered and return normal `404` responses.

A `503` is used only when service availability is actually involved.

## Deferred work

Later phases own:

- Hook management and immutable Hook Revisions;
- hook compilation;
- Bundles, publication, and compiled artifacts;
- compiled Bundle runtime endpoints and ETag support;
- v2 import and export;
- n8n integration changes;
- `UsingSession/localai` image updates;
- project-specific prompts and seed data.
