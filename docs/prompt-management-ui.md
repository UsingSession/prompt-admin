# Prompt Management UI

## Status

Phase 3B implements the server-rendered Prompt-domain administration interface
and Prompt Revision comparison.

## Architecture

```text
Browser
-> FastAPI UI route
-> existing Pydantic boundary schema
-> Prompt-domain service
-> explicit psycopg repository
-> PostgreSQL
```

The UI router is registered separately from `/api/v1` and is excluded from
OpenAPI. The management API contract therefore remains unchanged.

UI handlers do not:

- issue loopback HTTP requests;
- execute SQL;
- reimplement lifecycle rules;
- mutate immutable Revisions;
- depend on JavaScript for core operations.

## Application shell

`templates/base.html` provides:

- document metadata;
- Prompt Admin branding;
- active navigation;
- shared CSS;
- status messages;
- the main content block.

Navigation includes only implemented features:

```text
Dashboard
Prompts
Families
Deleted Records
FastAPI documentation
```

## Form handling

Forms use standard `GET` and `POST` methods.

```text
POST
-> parse application/x-www-form-urlencoded body
-> construct existing Pydantic schema
-> call Prompt-domain service
-> 303 See Other
-> render the resulting GET page
```

No JavaScript method tunnelling is used.

Pydantic validation errors are rendered with submitted safe values and
field-level messages. Domain errors use `PromptAdminError` messages without
exposing database details.

## Families

The UI supports:

- active, deleted, and combined lists;
- create;
- metadata detail;
- metadata update;
- soft delete;
- restore;
- associated Prompt display.

`family_key` is writable only during creation.

## Prompts

The UI supports:

- deterministic list;
- Family filter;
- category filter;
- active, deleted, and combined lifecycle filter;
- create with optional Family;
- metadata detail;
- metadata update;
- soft delete;
- restore;
- Variant list.

Prompt metadata forms do not accept Prompt text. `prompt_key` is writable only
during creation.

## Deleted Records

The basket is available at:

```http
GET /deleted
```

It lists soft-deleted Families and Prompts separately. Each record supports:

- restore;
- permanent deletion through a direct action button.

Permanent deletion is intentionally separate from soft deletion. A stable key
remains reserved while its record is in the basket. Deleting the record
permanently releases the key so a new record may use it.

Family permanent deletion:

- is allowed only after soft deletion;
- removes the Family row;
- detaches associated Prompts through the existing foreign-key behavior;
- does not delete associated Prompts.

Prompt permanent deletion:

- is allowed only after soft deletion;
- removes all Variants and immutable Revisions owned by the Prompt;
- is blocked when any Revision is referenced by a Bundle item;
- preserves the invariant that referenced immutable Revisions cannot be
  deleted.

Partial unique indexes are not used to permit duplicate active and deleted
stable keys. Such duplicates would make read and restore behavior ambiguous.

## Variants

The UI supports:

- create;
- metadata detail;
- metadata update;
- lifecycle transition between `draft`, `available`, and `archived`;
- deterministic Revision history.

Variant deletion is not implemented. Retirement uses `archived`.
`variant_key` is writable only during creation.

## Revisions

The UI supports:

- immutable Revision creation;
- exact submitted Prompt text;
- change note;
- detail page;
- deterministic history;
- optional copy from an old Revision into the create form.

Copying old content never changes the source Revision. Saving creates the next
immutable Revision.

Archived Variants remain readable but cannot receive new Revisions.

## Comparison

Comparison is scoped by the Prompt and Variant route:

```http
GET /prompts/{prompt_key}/variants/{variant_key}/compare
    ?from_revision=2
    &to_revision=5
```

The implementation uses `difflib`.

The page renders:

- metadata for both Revisions;
- unified diff;
- side-by-side rows;
- line numbers;
- preserved whitespace;
- detail links.

Comparison does not call a write service method.

Jinja2 autoescaping applies to Prompt and diff text. No Prompt content is marked
safe.

## Security

The existing exact local-origin middleware applies to UI writes.

Accepted hosts:

```text
localhost
127.0.0.1
::1
```

Prefix and subdomain matches are rejected.

All responses retain `Cache-Control: no-cache`.

Permanent deletion uses the same Origin or Referer validation as other UI
writes and remains restricted to records that were soft-deleted first.

## Testing

Run:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

UI route tests use service mocks for HTTP boundary behavior. Separate
PostgreSQL integration tests verify the real HTML create, redirect, detail,
Revision, archived-state, comparison, restore, permanent-deletion, key-reuse,
and reference-protection flows.

## Deferred work

This phase does not implement:

- Hooks;
- Hook Revisions;
- compilation;
- Bundles;
- publication;
- runtime retrieval;
- ETag support;
- import/export;
- authentication;
- frontend frameworks;
- `UsingSession/localai` changes.
