# Prompt Admin v2 Prompt Domain API

## Scope

Phase 3A implements backend management for Prompt Families, Prompts, Prompt
Variants, and immutable Prompt Revisions.

The server-rendered management UI is deferred to Phase 3B.

## Domain terminology

- **Family** is optional organizational metadata.
- **Prompt** is a stable logical task and input/output contract.
- **Variant** is an alternative implementation of the same Prompt contract.
- **Revision** is an immutable content snapshot of one Variant.

Prompt text is stored only in `ai_prompt_revisions`. It is never stored on
`ai_prompts`.

## Stable keys

`family_key`, `prompt_key`, and `variant_key`:

- are immutable after creation;
- must contain visible characters;
- must not contain surrounding whitespace;
- must not exceed 120 characters;
- must not encode revisions using `_v1`, `_v2`, or similar suffixes.

Invalid keys are rejected. The API does not silently normalize them.

## Variant lifecycle

Accepted statuses are:

```text
draft
available
archived
```

`production` is not a Variant status. Production selection belongs to a future
published Bundle Revision.

All accepted status changes are reversible. An archived Variant retains its
history but cannot receive a new Prompt Revision until its status changes.

## Revision immutability and concurrency

Prompt Revisions are append-only. The API exposes create and read operations
only.

Revision creation runs in one explicit PostgreSQL transaction:

```text
lock Prompt row
-> verify Prompt is not deleted
-> lock Variant row
-> verify Variant is not archived
-> calculate MAX(revision_number) + 1
-> insert revision
-> commit
```

The Variant row lock serializes concurrent creation for one Variant. The unique
constraint on `(variant_id, revision_number)` remains the final safety boundary.

## Soft deletion

Family and Prompt deletion is soft deletion.

Normal list and read operations exclude deleted records. Restore endpoints are
available for administrative recovery.

Deleting a Family does not delete or detach its Prompts. Existing Prompt
references remain intact. A deleted Family cannot be assigned to a new or
updated Prompt.

A deleted Prompt cannot receive new Variants or Revisions.

## Endpoints

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

### Variants

```http
GET   /api/v1/prompts/{prompt_key}/variants
POST  /api/v1/prompts/{prompt_key}/variants
GET   /api/v1/prompts/{prompt_key}/variants/{variant_key}
PATCH /api/v1/prompts/{prompt_key}/variants/{variant_key}
```

### Revisions

```http
GET  /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions
POST /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions
GET  /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions/{revision}
```

No Prompt Revision update or delete endpoint exists.

## Examples

Create a Prompt:

```json
{
  "prompt_key": "chat.english_tutor.system",
  "display_name": "English tutor system",
  "description": "System contract for the tutor.",
  "category": "education",
  "family_key": "education.tutors"
}
```

Create a Variant:

```json
{
  "variant_key": "baseline",
  "display_name": "Baseline",
  "description": "Current reference implementation.",
  "status": "available"
}
```

Create a Revision:

```json
{
  "system_prompt": "You are an English tutor.",
  "change_note": "Initial revision"
}
```

Revision response:

```json
{
  "prompt_key": "chat.english_tutor.system",
  "variant_key": "baseline",
  "revision_number": 1,
  "system_prompt": "You are an English tutor.",
  "change_note": "Initial revision",
  "created_at": "2026-07-23T10:00:00+00:00"
}
```

## HTTP status and error codes

The API uses the existing error envelope:

```json
{
  "error": {
    "code": "prompt_not_found",
    "message": "Prompt was not found."
  }
}
```

Stable domain codes include:

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

Validation failures return `422`. Duplicate keys and invalid lifecycle states
return `409`. Missing resources return `404`. Database connectivity failures
return `503`. Unexpected failures remain generic `500` responses.

## Transitional routes

`GET /api/prompts/compiled` remains a controlled `503` transitional route.
Legacy server-rendered domain pages remain unavailable. `GET /healthz` and
normal unknown-route `404` behavior remain unchanged.

## Deferred work

Phase 3B and later phases own:

- server-rendered CRUD pages;
- revision comparison UI;
- Hooks and Hook Revisions;
- Bundles, publication, and compiled artifacts;
- runtime Bundle endpoints;
- v2 import and export;
- n8n integration.
