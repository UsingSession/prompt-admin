# FastAPI Foundation

## Status

Implemented as Prompt Admin v2 Phase 1.

This phase replaces the Python standard-library HTTP server without changing
Prompt Admin's current database schema or domain model.

## Runtime architecture

```text
Uvicorn
-> FastAPI application factory
-> FastAPI routes
-> existing repositories and compiler
-> PostgreSQL
```

The application is created through:

```python
app.create_app()
```

Uvicorn is the production entrypoint. The Docker image starts:

```text
uvicorn app:create_app --factory
```

## Startup

FastAPI lifespan startup calls the existing `init_database()` function. Schema
initialization and SQL migration behavior remain unchanged in Phase 1.

## Configuration

`config.Settings` validates environment configuration at process startup.

Supported variables:

```text
PROMPT_ADMIN_HOST
PROMPT_ADMIN_PORT
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
```

Ports must be between `1` and `65535`. Required string values must not be empty.

## HTTP behavior

The existing UI and compiled prompt routes are registered directly as FastAPI
routes. The old `BaseHTTPRequestHandler` adapter is not retained.

Static files are mounted through Starlette `StaticFiles` at `/static`.

Jinja2 is configured through `Jinja2Templates` and is used for common framework
error pages. Existing feature templates still use the current rendering module;
converting all templates to Jinja2 is intentionally deferred to a separate,
reviewable change.

API errors use this shape:

```json
{
  "error": {
    "code": "not_found",
    "message": "Resource not found."
  }
}
```

UI errors return server-rendered HTML.

## Health endpoint

```http
GET /healthz
```

Healthy response:

```json
{
  "status": "ok",
  "database": true
}
```

A database failure returns HTTP `503` with `status` set to `degraded`.

## Validation

Install development dependencies and run tests:

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -p "test_*.py"
```

Build the image:

```bash
docker build -t prompt-admin:local .
```

The GitHub Actions test workflow runs the complete unit-test suite for pull
requests and pushes to `main`.

## Deferred work

This phase does not include:

- the Prompt Admin v2 database schema;
- Prompt, Variant, or Revision entities;
- bundles or publication;
- immutable compiled artifacts;
- runtime bundle endpoints;
- v2 import or export;
- n8n changes;
- a `localai` image version update.
