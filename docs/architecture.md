# LocalAI Architecture

## System Overview

`UsingSession/localai` is a local AI infrastructure and orchestration platform.

Its primary runtime services are:

```text
Windows host
└─ LM Studio

Docker
├─ Open WebUI
├─ n8n
├─ PostgreSQL
├─ Qdrant
├─ SearXNG
└─ Prompt Admin
```

The architecture separates user interaction, workflow orchestration, prompt
management, persistent storage, vector retrieval, web retrieval, and model
inference.

## High-Level Data Flow

The standard conversational workflow follows this pattern:

```text
User
-> Open WebUI
-> Pipe
-> Parent n8n workflow
-> Child n8n workflow
-> Prompt Admin and/or model backend
-> Child result
-> Parent response
-> Open WebUI
-> User
```

The exact child workflow depends on the normalized request mode.

## Components and Responsibilities

### Open WebUI

Open WebUI is the primary chat interface and gateway.

Responsibilities:

- collect user input;
- provide chat history and user context;
- attach files and request metadata;
- invoke the configured Pipe;
- display the final workflow response;
- expose configured local or remote model access.

Open WebUI should not contain domain-specific workflow orchestration logic.

### Pipe

The Pipe is the request parser and normalizer between Open WebUI and n8n.

Responsibilities:

- accept Open WebUI input;
- parse slash commands;
- determine the workflow mode;
- preserve the original input;
- create cleaned workflow input;
- parse supported option lines;
- forward files, history, user data, and context;
- send a normalized payload to the parent n8n webhook.

Command parsing belongs in Pipe.

It must not be duplicated in the parent workflow, `GLOBAL.js`, or child
workflows.

### Parent n8n Workflow

The parent workflow is a shared state builder and router.

Canonical pattern:

```text
Webhook
-> GLOBAL.js
-> Switch by mode
-> Execute child workflow
-> Return child result
```

Responsibilities:

- validate and normalize the incoming payload;
- build the shared state object;
- separate original input from cleaned input;
- normalize parsed options;
- expose shared model and request context;
- route the request by mode;
- return the child workflow output.

The parent workflow should not contain domain-specific generation logic.

### `GLOBAL.js`

`GLOBAL.js` builds the canonical state consumed by child workflows.

It trusts values already prepared by Pipe, including:

```text
payload.mode
payload.command
payload.input.text
payload.input.raw_text
```

Canonical concepts:

```text
state.input.original = original or debug input
state.input.text = cleaned workflow input
state.options = parsed options
mode = workflow route
```

`GLOBAL.js` must not maintain an independent slash-command map.

### Child n8n Workflows

Child workflows contain domain-specific business logic.

Responsibilities may include:

- prompt retrieval;
- model calls;
- structured parsing;
- retrieval planning;
- embedding generation;
- Qdrant queries;
- result normalization;
- output formatting.

A child workflow receives the complete normalized item.

Typical fields include:

```js
$json.mode
$json.state.input.text
$json.state.input.files
$json.state.options
$json.state.model
```

Child workflows must not repeat command or option parsing already completed by
Pipe or the parent workflow.

### Prompt Admin

Prompt Admin is a standalone, generic prompt-management service.

The current Phase 3B implementation is responsible for:

- managing Prompt Families as human-facing organizational metadata;
- managing Prompts as stable logical tasks and input/output contracts;
- managing Prompt Variants as alternative implementations of one Prompt
  contract;
- creating and reading immutable Prompt Revisions;
- exposing the versioned `/api/v1` Prompt-domain management API;
- providing a server-rendered administration UI for the Prompt domain;
- providing unified and side-by-side Prompt Revision comparison;
- providing a Deleted Records basket for soft-deleted Families and Prompts;
- enforcing guarded permanent deletion for already soft-deleted records;
- validating API and HTML form boundaries with Pydantic;
- enforcing lifecycle rules through domain services;
- executing explicit parameterized SQL through PostgreSQL repositories;
- managing its database schema, migrations, tests, Dockerfile, and releases.

The active API request flow is:

```text
FastAPI API route
-> Pydantic boundary schema
-> Prompt-domain service
-> explicit PostgreSQL repository
-> Prompt Admin v2 schema
```

The active browser UI flow is:

```text
Browser
-> FastAPI UI route
-> parse path, query, or URL-encoded form data
-> existing Pydantic schema
-> Prompt-domain or Deleted Records service
-> explicit PostgreSQL repository
-> Jinja2 response or 303 redirect
```

UI routes do not issue loopback HTTP requests to `/api/v1`, execute SQL, or
reimplement Prompt lifecycle rules. Core administration does not depend on
JavaScript.

The following are not implemented yet:

- Hook and immutable Hook Revision management and compilation (Phase 4);
- Prompt Bundles, Bundle Revisions, publication, and Compiled Artifacts
  (Phase 5);
- the final Bundle runtime API and ETag support (Phase 6);
- v2 import and export and remaining administration enhancements (Phase 7).

PostgreSQL is the source of truth for the Prompt Admin v2 schema. The active
application manages:

```text
Prompt Families
Prompts
Prompt Variants
Prompt Revisions
Deleted Family and Prompt lifecycle
```

Prompt text is stored only in Prompt Revisions. Prompt rows contain metadata
only.

Soft-deleted Families and Prompts remain addressable for restoration. Their
stable keys remain reserved until permanent deletion. Permanent deletion is
available only after soft deletion.

Family permanent deletion detaches associated Prompts through the existing
foreign-key behavior and does not delete those Prompts. Prompt permanent
deletion removes owned Variants and immutable Revisions, but is blocked when a
Revision is referenced by a Bundle item.

n8n must not read Prompt Admin tables directly from PostgreSQL. The final
runtime retrieval contract is not currently implemented, so n8n migration to
Prompt Admin v2 remains pending.

The target runtime endpoint remains:

```http
GET /api/v1/bundles/{bundle_key}/compiled
```

This target endpoint is not part of Phase 3B.

Prompt Families are grouping metadata for administration. They are not:

- revision chains;
- runtime selectors;
- production pointers;
- Prompt Bundles;
- runtime API units.

### PostgreSQL

PostgreSQL provides structured persistent storage.

It is used for:

- n8n database state;
- Prompt Admin data;
- structured workflow or application state where appropriate.

PostgreSQL data ownership should remain explicit. A consumer should use a
service API instead of reading another service's internal tables directly.

### Qdrant

Qdrant provides vector storage and retrieval.

It is used for:

- embeddings;
- semantic search;
- RAG collections;
- project-specific vector datasets.

Qdrant is reusable infrastructure, while its collections and datasets may
remain project-specific.

### SearXNG

SearXNG provides optional local web search and retrieval.

It should remain an optional platform capability rather than a required
dependency for every workflow.

### LM Studio

LM Studio runs as a normal Windows host application.

It is not part of the Docker Compose stack.

Endpoints:

```text
Windows host:
http://localhost:1234/v1

Docker containers:
http://host.docker.internal:1234/v1
```

Stable container configuration:

```env
LM_STUDIO_API_URL=http://host.docker.internal:1234/v1
```

LM Studio exposes an OpenAI-compatible API for local model inference.

## Repository Boundaries

### `UsingSession/localai`

Owns:

- Docker Compose;
- infrastructure configuration;
- service versions;
- networking;
- PostgreSQL service configuration;
- backup and restore tooling;
- tray integration;
- developer scripts;
- Open WebUI integration;
- n8n integration;
- Qdrant integration;
- SearXNG integration;
- Prompt Admin runtime integration;
- pinned external service images.

Does not own:

- Prompt Admin application source code;
- Prompt Admin migrations;
- Prompt Admin tests;
- Prompt Admin image publishing workflow.

### `UsingSession/prompt-admin`

Owns:

- Prompt Admin application code;
- UI and API;
- schema and migrations;
- tests;
- Dockerfile;
- GitHub Actions;
- Docker image releases.

Does not own:

- the complete `localai` Compose stack;
- `localai` infrastructure orchestration;
- project-specific prompts or datasets.

## Prompt Admin Runtime Integration

Normal `localai` usage consumes a pinned Prompt Admin image:

```yaml
prompt-admin:
  image: ${PROMPT_ADMIN_IMAGE}:${PROMPT_ADMIN_VERSION}
```

Recommended environment model:

```env
PROMPT_ADMIN_IMAGE=ghcr.io/usingsession/prompt-admin
PROMPT_ADMIN_VERSION=<pinned-version>
```

The service remains configured by `localai`, including:

- networking;
- ports;
- PostgreSQL connection;
- dependencies;
- runtime environment.

A local development build should use a separate Compose override that points to
a sibling `prompt-admin` repository.

```yaml
services:
  prompt-admin:
    image: prompt-admin:dev
    build:
      context: ../prompt-admin
```

This creates two explicit modes:

```text
Normal usage
-> pinned published image

Prompt Admin development
-> local sibling repository build
```

## Prompt Admin Application Architecture

Prompt Admin uses FastAPI as its HTTP application framework and Uvicorn as its
ASGI runtime.

The application is created through a FastAPI application factory:

```text
app.create_app()
```

Startup follows this flow:

```text
Uvicorn
-> FastAPI application factory
-> lifespan startup
-> PostgreSQL schema initialization and ordered migrations
-> API and UI router registration
```

The current API path is:

```text
FastAPI API route
-> Pydantic boundary schema
-> Prompt-domain service
-> explicit PostgreSQL repository
-> PostgreSQL
```

The current UI path is:

```text
FastAPI UI route
-> parse path, query, or application/x-www-form-urlencoded data
-> construct an existing Pydantic schema
-> Prompt-domain or Deleted Records service
-> explicit PostgreSQL repository
-> render Jinja2 or return 303 See Other
```

Current active responsibilities are separated as follows:

```text
app.py
-> application creation
-> lifespan wiring
-> static-file mounting
-> common middleware
-> exception handling

routes.py
-> registers Prompt-domain API routes
-> registers Prompt management UI routes
-> registers Deleted Records UI routes
-> exposes GET /healthz

api/prompt_management.py
-> versioned /api/v1 route handlers
-> HTTP request and response mapping

ui/prompt_management.py
-> dashboard and Prompt-domain HTML routes
-> URL-encoded form parsing
-> Post/Redirect/Get handling
-> Jinja2 context construction
-> Revision comparison through difflib

ui/deleted_records.py
-> Deleted Records basket routes
-> restore and permanent-delete actions

schemas/prompt.py
-> strict Pydantic API and form-boundary schemas
-> stable-key and lifecycle-value validation

services/prompt_service.py
-> Prompt-domain rules
-> transaction orchestration
-> stable domain error mapping

services/deleted_record_service.py
-> permanent-deletion lifecycle checks
-> reference protection and transaction orchestration

repositories/prompt_repository.py
-> explicit parameterized psycopg SQL
-> deterministic Prompt-domain row mapping and ordering

repositories/deleted_record_repository.py
-> deleted-record queries and guarded permanent deletion

db.py
-> connections, explicit transaction context, migrations, and health checks

templates/
-> inherited server-rendered Prompt-domain pages
-> HTML error pages

static/prompt-management.css
-> Phase 3B lifecycle, form, immutable-content, and diff presentation
```

Current application stack:

```text
FastAPI
Uvicorn
Jinja2
Pydantic
psycopg
SQL migrations
plain CSS
minimal vanilla JavaScript enhancements
Python difflib
```

The following remain intentionally excluded:

```text
No ORM
No Alembic
No frontend framework
No generic repository framework
No generic CMS
No background worker
No message queue
```

Jinja2 renders the active Prompt-domain administration pages and framework-level
HTML errors. Templates use inheritance through `templates/base.html`.
Jinja2 autoescaping remains enabled; Prompt and diff content is never marked as
trusted HTML.

Core management works without JavaScript. HTML mutations use normal POST routes
and Post/Redirect/Get with `303 See Other`. The UI reuses existing Pydantic
schemas and services instead of calling `/api/v1` through loopback HTTP.

Static assets are served through Starlette `StaticFiles`.

Configuration is validated during process startup. Supported environment
variables include:

```text
PROMPT_ADMIN_HOST
PROMPT_ADMIN_PORT
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
```

Database passwords are preserved exactly and are not whitespace-normalized.

API errors use a machine-readable envelope:

```json
{
  "error": {
    "code": "prompt_not_found",
    "message": "Prompt was not found."
  }
}
```

Non-API errors and invalid UI resources use server-rendered HTML responses.
HTML form errors preserve safe submitted values and display field or summary
messages without exposing database details.

Responses include:

```text
Cache-Control: no-cache
```

Browser write requests using `POST`, `PUT`, `PATCH`, or `DELETE` validate the
`Origin` header when present and otherwise validate `Referer`. Requests are
accepted only from exact local hosts:

```text
localhost
127.0.0.1
::1
```

HTTP and HTTPS are supported. Prefix matches such as
`localhost.example.com` are rejected. Requests without `Origin` or `Referer`
remain supported for local non-browser clients.

Multi-check writes use `db.transaction()`. Successful operations commit after
the transaction context exits. Failures roll back and close cursors and
connections safely.

Revision creation serializes numbering for one Prompt Variant by locking the
Prompt row and then the Variant row with `SELECT ... FOR UPDATE` before
calculating `MAX(revision_number) + 1` and inserting the immutable Revision.
The unique `(variant_id, revision_number)` constraint remains the final safety
boundary. No retry loop hides transaction-design errors.

The initial deployment remains local-only and does not require authentication.
Authentication must be added before LAN or public exposure.

## Current Prompt Domain Management Contracts

### Server-rendered administration UI

The root path is the active Prompt Admin dashboard:

```http
GET /
```

Active navigation contains only implemented features:

```text
Dashboard
Prompts
Families
Deleted Records
FastAPI documentation
```

The FastAPI documentation link uses `/docs`; the removed custom `/api-docs`
route is not restored.

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

The comparison route accepts explicit `from_revision` and `to_revision` query
parameters. It loads only Revisions belonging to the Prompt Variant identified
by the route and performs no writes.

Revision comparison uses Python `difflib` and provides unified and side-by-side
diffs, line numbers, preserved whitespace, metadata, and links to both Revision
detail pages. When fewer than two Revisions exist, the page presents an empty
state.

### Versioned management API

The `/api/v1` Prompt-domain management API remains unchanged by Phase 3B.

Prompt Families:

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

Prompt Variants:

```http
GET   /api/v1/prompts/{prompt_key}/variants
POST  /api/v1/prompts/{prompt_key}/variants
GET   /api/v1/prompts/{prompt_key}/variants/{variant_key}
PATCH /api/v1/prompts/{prompt_key}/variants/{variant_key}
```

Prompt Revisions:

```http
GET  /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions
POST /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions
GET  /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions/{revision}
```

Prompt Revisions are append-only immutable snapshots. History is returned in
ascending Revision order. No Revision `PATCH`, `PUT`, or `DELETE` endpoint,
service method, or repository mutation method exists.

A Prompt Variant supports mutable metadata and lifecycle status updates. The
allowed statuses are:

```text
draft
available
archived
```

`production` is not a Variant status. Production selection belongs to a future
published Bundle Revision. An archived Variant retains its Revision history but
cannot receive new Revisions.

Stable keys are rejected when they are empty, contain surrounding whitespace,
exceed the schema limit, or encode a Revision suffix such as `_v1`. Invalid
keys are not silently normalized. Unsupported request fields are rejected.
Prompt text is accepted only when creating a Prompt Revision.

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

Known database constraints are mapped without exposing SQL statements, table
names, connection details, raw PostgreSQL messages, or stack traces.

### Deleted Records and permanent deletion

Families and Prompts use soft deletion and explicit restoration. A soft-deleted
record remains in the Deleted Records basket and retains its stable key.

Permanent deletion is available only for already soft-deleted records:

- permanent Family deletion removes the Family row, detaches associated Prompts
  through the existing foreign-key behavior, and does not delete those Prompts;
- permanent Prompt deletion removes its owned Variants and immutable Revisions;
- permanent Prompt deletion is blocked when any owned Revision is referenced by
  a Bundle item;
- permanent deletion releases the stable key for future reuse;
- duplicate active and deleted stable keys are not allowed because they would
  make reads and restoration ambiguous.

### Removed pre-v2 and runtime routes

The root path is no longer a removed route; it is the Phase 3B dashboard.

Removed pre-v2 routes such as the following remain unregistered:

```text
/delete
/api-docs
/api/prompts/compiled
/save
```

They return normal `404 Not Found` responses. They are not compatibility or
transitional contracts, and there is no `legacy_domain_unavailable` response.
HTTP `503` is reserved for actual service or database unavailability, including
a degraded `/healthz` response or an operation that PostgreSQL cannot serve.

The application currently has no final runtime prompt-retrieval endpoint. The
target remains:

```http
GET /api/v1/bundles/{bundle_key}/compiled
```

That endpoint depends on Prompt Bundles, publication, and immutable Compiled
Artifacts and is not implemented in Phase 3B.


## Data Ownership

The architecture uses explicit ownership rules:

```text
Prompt Admin prompt data
-> Prompt Admin PostgreSQL schema
-> accessed through Prompt Admin API

n8n internal state
-> PostgreSQL

Vector and RAG data
-> Qdrant

Project-specific configuration and datasets
-> owned by the relevant project

Model runtime
-> LM Studio on the Windows host
```

A service should not bypass another service's public contract to access its
internal state.

## Docker and Host Boundaries

Docker contains infrastructure services.

LM Studio remains outside Docker on the Windows host.

Containers access host services through:

```text
host.docker.internal
```

Local administration services should bind to `127.0.0.1` unless public access is
explicitly required.

Secrets and encryption keys must remain outside version control.

## Backup and Restore Architecture

Backup is manual and explicit.

Starting the stack must not automatically trigger a backup.

Critical backup targets include:

- PostgreSQL dump;
- n8n workflow export;
- n8n credentials export;
- `.env` and required secrets;
- `N8N_ENCRYPTION_KEY`.

The critical n8n restore pair is:

```text
PostgreSQL dump + N8N_ENCRYPTION_KEY
```

The persistent n8n volume may contain additional internal state, but database
backups and the matching encryption key are required for restoring
database-backed workflows and credentials.

## Claude Code Backend Switching

`localai` provides a configurable Claude Code CLI switcher.

Commands:

```powershell
cc a
cc l
cc c
```

Backends:

```text
cc a
-> Anthropic Claude through Claude Pro OAuth

cc l
-> LM Studio through Open WebUI

cc c
-> Ollama Cloud Pipe through Open WebUI
```

Additional Claude Code arguments are forwarded to the selected backend.

Mutable configuration is stored outside the repository:

```text
%LOCALAPPDATA%\local-ai\claude-cli.json
```

The PowerShell profile should contain only the stable `cc` function.

## Architectural Rules

1. Pipe owns command parsing.
2. The parent workflow owns shared state construction and routing.
3. Child workflows own domain-specific business logic.
4. Prompt Admin owns Prompt Families, Prompts, Prompt Variants, Prompt
   Revisions, their administration UI, and the future Hook and Bundle domains.
5. PostgreSQL is used for structured persistent state.
6. Qdrant is used for vector and RAG storage.
7. Runtime consumers use Prompt Admin service APIs and never read Prompt Admin
   tables directly.
8. Service internals must not be accessed through another service's database
   tables.
9. Normal runtime should use pinned images.
10. Development builds should use explicit overrides.
11. Project-specific logic must not redefine the generic platform.
12. Reusable capabilities should be implemented through stable contracts.
13. Prompt Admin uses FastAPI and Uvicorn for its HTTP application layer.
14. FastAPI lifespan startup owns database schema initialization and migration
    execution.
15. Prompt-domain management APIs are versioned under `/api/v1`.
16. Server-rendered UI routes are separate from `/api/v1`, excluded from
    OpenAPI, and call the same domain services directly.
17. Core Prompt administration works without JavaScript and uses
    Post/Redirect/Get for HTML mutations.
18. Prompt rows contain metadata only; Prompt content is stored in immutable
    Prompt Revisions.
19. Prompt Revisions are append-only and expose no update or delete contract.
20. Production selection belongs to future published Prompt Bundles, not to a
    Prompt Variant status.
21. Concurrent Prompt Revision creation is serialized by row locking the
    Prompt and Prompt Variant before allocating the next Revision number.
22. Families and Prompts use soft deletion and explicit restoration.
23. Permanent deletion is available only after soft deletion and must preserve
    references to immutable Revisions.
24. Permanent Family deletion detaches associated Prompts but does not delete
    them.
25. Permanent Prompt deletion is blocked when an owned Revision is referenced
    by a Bundle item.
26. Jinja2 autoescaping remains enabled; Prompt and diff content must not be
    inserted as trusted HTML.
27. Removed pre-v2 routes are not compatibility contracts and return normal
    `404` responses.
28. The root path is the active Prompt Admin dashboard.
29. The current application has no final runtime Prompt retrieval endpoint.
30. The target runtime unit is an immutable published Bundle Compiled Artifact
    retrieved through `/api/v1/bundles/{bundle_key}/compiled`.
31. Prompt Admin browser write operations accept only exact local origins.
