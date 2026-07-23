# Prompt Admin

Prompt Admin is a local, generic prompt-management service backed by
PostgreSQL. It owns prompt-management application logic, UI and API behavior,
database migrations, tests, Docker image construction, and releases.

Prompt Admin does not own workflow graphs, model calls, Qdrant datasets,
project-specific prompts, or `UsingSession/localai` orchestration.

## Current implementation

Prompt Admin v2 Phase 3A provides:

- FastAPI application factory and Uvicorn runtime;
- lifespan-based PostgreSQL initialization;
- a clean v2 database schema;
- explicit `psycopg` SQL and transaction helpers;
- Prompt Family management API;
- Prompt metadata management API;
- Prompt Variant management API;
- immutable Prompt Revision creation and history;
- concurrency-safe revision numbering;
- stable domain error codes;
- Pydantic request and response schemas;
- real PostgreSQL domain tests;
- Docker startup and health smoke tests.

The server-rendered management UI, Hooks, Bundles, publication, compiled
artifacts, and runtime Bundle API are implemented in later phases.

## Local URL

```text
http://localhost:8090
```

Health check:

```http
GET /healthz
```

OpenAPI:

```text
http://localhost:8090/docs
http://localhost:8090/openapi.json
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

Detailed API, domain, error, soft-delete, and concurrency behavior is documented
in:

```text
docs/prompt-domain-api.md
```

## Management API

### Families

```http
GET    /api/v1/families
POST   /api/v1/families
GET    /api/v1/families/{family_key}
PATCH  /api/v1/families/{family_key}
DELETE /api/v1/families/{family_key}
POST   /api/v1/families/{family_key}/restore
```

### Prompts

```http
GET    /api/v1/prompts
POST   /api/v1/prompts
GET    /api/v1/prompts/{prompt_key}
PATCH  /api/v1/prompts/{prompt_key}
DELETE /api/v1/prompts/{prompt_key}
POST   /api/v1/prompts/{prompt_key}/restore
```

### Variants and Revisions

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

## Stable keys

`family_key`, `prompt_key`, and `variant_key` are immutable after creation.

The API rejects:

- empty or whitespace-only keys;
- surrounding whitespace;
- keys longer than 120 characters;
- revision suffixes such as `_v1` and `_v2`.

Invalid keys are not silently normalized.

## Revision concurrency

Revision creation executes in one PostgreSQL transaction:

```text
lock Prompt row
-> verify Prompt state
-> lock Variant row
-> verify Variant state
-> calculate the next revision number
-> insert the immutable Revision
-> commit
```

The Variant row lock serializes concurrent revision creation for one Variant.
The unique `(variant_id, revision_number)` constraint remains the final safety
boundary.

## Database initialization

The PostgreSQL database was intentionally reset before Phase 2. No legacy data
migration, conversion, backup, or compatibility path is implemented.

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
transaction lock before schema initialization and validates migration metadata
against the expected v2 tables.

Recovery and schema details:

```text
docs/v2-database-recovery.md
docs/v2-database-schema.md
```

## Transactions and repositories

`db.transaction()`:

- opens one connection and cursor;
- commits only after the context exits successfully;
- rolls back when an exception escapes;
- closes the cursor and connection in all cases.

Prompt-domain responsibilities follow:

```text
api/
-> HTTP parsing and response mapping

schemas/
-> request validation and serialization

services/
-> domain rules and transaction orchestration

repositories/
-> explicit parameterized SQL and row mapping
```

No ORM, Alembic, generic repository framework, or frontend framework is used.

## Transitional route behavior

The removed legacy schema cannot support the legacy administration routes.
Until the corresponding v2 phases are implemented:

- `GET /api/prompts/compiled` returns HTTP `503` with error code
  `legacy_domain_unavailable`;
- legacy UI routes return a server-rendered HTTP `503` page;
- cross-site browser write protection remains active;
- unknown API and UI routes remain normal `404` responses;
- `GET /healthz` remains functional.

The target runtime endpoint is deferred:

```http
GET /api/v1/bundles/{bundle_key}/compiled
```

## Tests

Install development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the complete test suite against a dedicated PostgreSQL database:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

GitHub Actions provisions PostgreSQL and verifies:

- fresh empty-database initialization;
- v2 schema constraints and migration metadata;
- Prompt Family, Prompt, Variant, and Revision behavior;
- soft-delete filtering and restoration;
- stable API errors and OpenAPI registration;
- transaction rollback;
- concurrent sequential revision creation;
- idempotent and serialized startup;
- controlled legacy route behavior;
- Docker image build;
- concurrent Docker startup and `GET /healthz`.

## Deferred work

Phase 3B and later phases own:

- server-rendered Prompt Admin CRUD pages;
- revision comparison UI;
- Hook management and Hook Revisions;
- hook compilation;
- Bundles, publication, and compiled artifacts;
- compiled Bundle runtime endpoints and ETag support;
- v2 import and export;
- n8n integration changes;
- `UsingSession/localai` image updates;
- project-specific prompts and seed data.
