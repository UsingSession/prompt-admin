# Prompt Admin

Prompt Admin is a local, generic prompt-management service backed by
PostgreSQL. It provides a server-rendered administration UI and an HTTP API for
runtime consumers such as n8n.

Prompt Admin owns prompt-management application logic, UI and API behavior,
database migrations, tests, Docker image construction, and releases. It does
not own workflow graphs, model calls, Qdrant datasets, or project-specific
prompts.

## Current implementation

Prompt Admin v2 Phase 1 establishes the FastAPI foundation while preserving the
current prompt, family, hook, compilation, import, and export domain behavior.

Current stack:

- FastAPI application factory;
- Uvicorn runtime;
- server-rendered HTML;
- Jinja2 wiring for framework error pages;
- existing template renderer for current feature pages;
- plain CSS and minimal vanilla JavaScript;
- explicit PostgreSQL access through `psycopg`;
- SQL schema and migrations;
- no ORM;
- no frontend framework;
- no authentication for the initial local-only deployment.

The accepted Prompt Admin v2 domain redesign is implemented in later phases.
Phase 1 does not add variants, immutable revisions, bundles, publication, or
compiled bundle artifacts.

## Runtime flow

```text
Runtime consumer
-> Prompt Admin API
-> repositories and compiler
-> PostgreSQL
```

Consumers must use Prompt Admin's HTTP API. They must not query Prompt Admin
PostgreSQL tables directly.

## Local URL

```text
http://localhost:8090
```

Health check:

```text
http://localhost:8090/healthz
```

The service is local-only. Bind it to `127.0.0.1` through the infrastructure
repository and do not expose it publicly without adding authentication and
other deployment controls.

## Configuration

Supported environment variables:

```text
PROMPT_ADMIN_HOST=0.0.0.0
PROMPT_ADMIN_PORT=8090
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=local_password
```

Configuration is validated at startup. Ports must be valid TCP port numbers,
and required string values must not be empty.

## Application entrypoint

Application factory:

```python
from app import create_app

app = create_app()
```

Development run:

```bash
uvicorn app:create_app --factory --host 0.0.0.0 --port 8090
```

The Docker image uses the same Uvicorn factory entrypoint.

## Current features

Prompt Admin currently supports:

- prompt CRUD;
- prompt families;
- reusable prompt hooks;
- active and inactive states;
- soft delete and restore;
- history snapshots;
- compiled prompt preview;
- JSON import and export;
- compiled prompt retrieval through the current runtime API.

A fresh database contains schema and migration metadata only. The application
does not create project-specific starter records.

## Current runtime endpoint

The current pre-v2 runtime endpoint remains available during Phase 1:

```http
GET /api/prompts/compiled
```

At least one selector is required:

```text
?category=general
?key=assistant_rules&key=response_formatter
?keys=assistant_rules,response_formatter
?category=general&keys=assistant_rules,response_formatter
```

The endpoint returns active, non-deleted prompts with hook placeholders
compiled.

The future primary v2 runtime endpoint will be implemented in a later phase:

```http
GET /api/v1/bundles/{bundle_key}/compiled
```

## HTTP errors

API errors use a stable machine-readable envelope:

```json
{
  "error": {
    "code": "bad_request",
    "message": "Request could not be completed."
  }
}
```

UI errors return server-rendered HTML. Unexpected errors return generic client
messages while diagnostic details are logged locally.

## Important routes

| Route | Purpose |
| --- | --- |
| `/` | Prompt list. |
| `/new` | Create prompt form. |
| `/edit?key=<prompt_key>` | Edit prompt. |
| `/clone?key=<prompt_key>` | Clone prompt. |
| `/preview?key=<prompt_key>` | Compiled prompt preview. |
| `/history?key=<prompt_key>` | Prompt history. |
| `/families` | Prompt family list. |
| `/family?key=<family_key>` | Prompt family overview. |
| `/hooks` | Hook list. |
| `/api-docs` | Current runtime API help. |
| `/api/prompts/compiled` | Current compiled prompts API. |
| `/deleted` | Deleted records. |
| `/import` | JSON import. |
| `/export` | JSON export. |
| `/healthz` | Application and database health. |

## Database

Current tables:

| Table | Purpose |
| --- | --- |
| `ai_prompt_families` | Prompt family records. |
| `ai_system_prompts` | Current prompt records. |
| `ai_system_prompt_versions` | Prompt history snapshots. |
| `ai_prompt_hooks` | Current hook records. |
| `ai_prompt_hook_versions` | Hook history snapshots. |
| `prompt_admin_migrations` | Applied migration tracking. |

Database files:

```text
database/
├─ schema.sql
└─ migrations/
   ├─ 001_prompt_admin_metadata.sql
   ├─ 002_prompt_hooks.sql
   ├─ 003_prompt_families.sql
   └─ 004_prompt_storage_cleanup.sql
```

Phase 1 does not modify this schema.

## Project structure

```text
prompt-admin/
├─ app.py
├─ config.py
├─ routes.py
├─ db.py
├─ repository.py
├─ hook_repository.py
├─ compiler.py
├─ render.py
├─ validation.py
├─ exporting.py
├─ database/
├─ docs/
├─ static/
├─ templates/
└─ tests/
```

## Tests

Install development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the complete test suite:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Build the Docker image:

```bash
docker build -t prompt-admin:local .
```

GitHub Actions runs unit tests and a Docker build for pull requests.

## Phase 1 documentation

See:

```text
docs/fastapi-foundation.md
```

## Operational notes

- PostgreSQL is the source of truth for Prompt Admin records.
- Runtime consumers use the Prompt Admin API.
- Prompt Admin does not create domain-specific starter prompts.
- Backups must include the Prompt Admin PostgreSQL data.
- Prompt contents should not be logged by default.
- Released Docker image versions should be pinned by `UsingSession/localai`.
