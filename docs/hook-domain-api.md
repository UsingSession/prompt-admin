# Hook Domain API

## Purpose

The Hook domain stores reusable content fragments independently from Prompt
text. Hook metadata and immutable Hook Revision content are separate records.

```text
Hook metadata
└─ immutable Hook Revisions
```

## Terminology

A Hook is a stable logical definition identified by `hook_key`.

A Hook Revision is an immutable snapshot containing:

```text
hook_group
hook_content
priority
is_enabled
change_note
```

A Hook group is stored without the leading `#`:

```text
hook_global.response_rules
```

Prompt text references that group as:

```text
#hook_global.response_rules
```

## Lifecycle

Hooks support create, list, read, mutable metadata update, soft deletion, and
restoration. Permanent deletion is not part of Phase 4A.

Normal reads exclude deleted Hooks. `include_deleted=true` is an explicit
management operation. A deleted Hook cannot receive a new Revision and does not
contribute to compilation. Its stable key remains reserved.

Restoration makes the highest Hook Revision effective again according to that
Revision's `is_enabled` value.

## Stable keys

`hook_key` uses the shared stable-key contract:

- non-empty and not whitespace-only;
- no surrounding whitespace;
- maximum 120 characters;
- no `_v1`, `_v2`, or similar Revision suffix;
- immutable after creation;
- never silently normalized.

## Hook groups

Hook groups must match:

```text
hook_[A-Za-z0-9_.-]+
```

They must not include a leading `#`, whitespace, surrounding whitespace, or
more than 120 characters.

## Management API

Hooks:

```http
GET    /api/v1/hooks
POST   /api/v1/hooks
GET    /api/v1/hooks/{hook_key}
PATCH  /api/v1/hooks/{hook_key}
DELETE /api/v1/hooks/{hook_key}
POST   /api/v1/hooks/{hook_key}/restore
```

List filters:

```text
category
include_deleted
```

The single-Hook read supports `include_deleted=true` as an explicit deleted
record lookup.

Hook Revisions:

```http
GET  /api/v1/hooks/{hook_key}/revisions
POST /api/v1/hooks/{hook_key}/revisions
GET  /api/v1/hooks/{hook_key}/revisions/{revision}
```

No Hook Revision `PATCH`, `PUT`, or `DELETE` route exists.

## Immutable Revision contract

Revision numbering starts at `1` and increases within one Hook. History is
returned in ascending Revision order. Stored Hook content is returned exactly
as inserted.

Revision creation requires an existing non-deleted Hook, a valid Hook group,
non-whitespace Hook content, and a non-negative priority.

## Concurrency

Revision creation runs in one PostgreSQL transaction:

```text
SELECT Hook row FOR UPDATE
-> verify Hook lifecycle state
-> calculate MAX(revision_number) + 1
-> insert immutable Hook Revision
-> commit
```

The Hook row lock serializes concurrent Revision allocation for one Hook. The
unique `(hook_id, revision_number)` constraint remains the final safety
boundary. No retry loop hides transaction-design errors.

## Errors

Stable Hook and compiler error codes include:

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

Validation failures use HTTP `422`. Lifecycle conflicts use HTTP `409`.
Missing resources use HTTP `404`. PostgreSQL unavailability uses HTTP `503`.

Responses never expose SQL, table names, raw PostgreSQL messages, connection
information, stack traces, or Hook content in logs by default.

## Example

Create a Hook:

```json
{
  "hook_key": "global.response.no_markdown",
  "display_name": "Avoid Markdown",
  "description": "Reusable response-format rule",
  "category": "global"
}
```

Create its first Revision:

```json
{
  "hook_group": "hook_global.response_rules",
  "hook_content": "Return plain text without Markdown formatting.",
  "priority": 100,
  "is_enabled": true,
  "change_note": "Initial rule"
}
```

## Deferred work

Phase 4B owns the Hook administration UI, Revision comparison, impact views,
compiled-preview UI, and active Hooks navigation.
