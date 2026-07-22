# Prompt Admin

Prompt Admin is a local, generic prompt-management service backed by
PostgreSQL. It owns prompt-management application logic, UI and API behavior,
database migrations, tests, Docker image construction, and releases.

Prompt Admin does not own workflow graphs, model calls, Qdrant datasets,
project-specific prompts, or `UsingSession/localai` orchestration.

## Current implementation

Prompt Admin v2 Phase 2 provides:

- FastAPI application factory and Uvicorn runtime;
- lifespan-based PostgreSQL initialization;
- a clean v2 database schema;
- explicit `psycopg` SQL and transaction helpers;
- domain-specific repository foundations;
- real PostgreSQL schema tests;
- Docker startup and health smoke tests.

The administration UI, prompt CRUD, hook CRUD, bundles, publication, compiled
artifacts, and runtime bundle API are implemented in later phases.

## Local URL

```text
http://localhost:8090
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

Legacy migrations `001` through `004` were removed because they recreated the
pre-v2 tables on an empty database. Repeated startup is idempotent because
applied migration filenames are recorded in `prompt_admin_migrations`.

Startup acquires a PostgreSQL advisory transaction lock before schema
initialization. Multiple Prompt Admin processes therefore cannot apply the same
migration concurrently.

Startup also validates migration metadata against the expected v2 tables. It
fails with an explicit schema-state error when tables exist without metadata or
metadata references a schema with missing tables. Recovery is documented in:

```text
docs/v2-database-recovery.md
```

A fresh database contains only migration metadata and these v2 domain tables:

| Table | Purpose |
| --- | --- |
| `ai_prompt_families` | Human-facing prompt groups. |
| `ai_prompts` | Stable logical prompt identities. |
| `ai_prompt_variants` | Alternative implementations of a prompt contract. |
| `ai_prompt_revisions` | Immutable prompt snapshots. |
| `ai_hooks` | Stable hook identities. |
| `ai_hook_revisions` | Immutable hook snapshots. |
| `ai_prompt_bundles` | Stable runtime bundle identities. |
| `ai_prompt_bundle_revisions` | Versioned bundle mappings and publication state. |
| `ai_prompt_bundle_items` | Role-to-prompt-revision mappings. |
| `ai_compiled_bundle_artifacts` | One immutable artifact per bundle revision. |
| `prompt_admin_migrations` | Applied migration tracking. |

No default families, prompts, hooks, bundles, artifacts, converted records, or
project-specific data are inserted.

Detailed constraints, indexes, and deletion rules are documented in:

```text
docs/v2-database-schema.md
```

## Transactions and repositories

`db.transaction()`:

- opens one connection and cursor;
- commits only after the context exits successfully;
- rolls back when an exception escapes;
- closes the cursor and connection in all cases.

Phase 2 repository modules are intentionally small:

```text
repositories/
├─ prompt_repository.py
├─ hook_repository.py
├─ bundle_repository.py
└─ artifact_repository.py
```

They provide existence checks and revision-number query helpers only. They do
not implement Phase 3–5 CRUD or update immutable records.

## Transitional route behavior

The removed legacy schema cannot support the Phase 1 administration routes.
Until the corresponding v2 phases are implemented:

- `GET /api/prompts/compiled` returns HTTP `503` with error code
  `legacy_domain_unavailable`;
- legacy UI routes return a server-rendered HTTP `503` page;
- cross-site POST protection remains active;
- unknown API and UI routes remain normal `404` responses;
- `GET /healthz` remains functional.

The target runtime endpoint is deferred to Phase 6:

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
- expected v2 tables and migration metadata;
- absence of legacy tables and seed data;
- foreign-key, unique, and check constraints;
- transaction rollback;
- idempotent repeated startup;
- serialized concurrent startup;
- inconsistent migration-state rejection;
- controlled legacy route behavior;
- Docker image build;
- concurrent Docker startup against PostgreSQL;
- `GET /healthz` on both containers.

## Deferred work

Phase 2 does not implement:

- administration UI and prompt management;
- variant or revision CRUD;
- hook compiler redesign;
- bundle publication;
- runtime compiled bundle endpoints;
- v2 import or export;
- n8n changes;
- `UsingSession/localai` image updates;
- project-specific seed data.
