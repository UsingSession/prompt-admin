# Prompt Admin v2 Database Schema

## Status

Prompt Admin v2 Phase 2 database foundation.

The PostgreSQL database was intentionally cleared before this phase. This
implementation does not migrate, convert, back up, or preserve pre-v2 domain
data.

## Initialization strategy

`database/schema.sql` creates only:

```text
prompt_admin_migrations
```

`db.init_database()` then applies unapplied SQL files from
`database/migrations/` in filename order inside one transaction.

The v2 baseline is:

```text
005_prompt_model_v2.sql
```

Legacy migrations `001` through `004` were removed. Retaining them would create
the legacy domain tables before the v2 migration on every completely empty
database.

The migration metadata table is retained across normal startup. The migration
filename is inserted only after its SQL completes successfully. A failed
migration rolls back together with its metadata write.

Repeated startup is idempotent because an applied migration is skipped when its
filename is already present in `prompt_admin_migrations`.

## Tables

The v2 baseline creates:

```text
ai_prompt_families
ai_prompts
ai_prompt_variants
ai_prompt_revisions
ai_hooks
ai_hook_revisions
ai_prompt_bundles
ai_prompt_bundle_revisions
ai_prompt_bundle_items
ai_compiled_bundle_artifacts
```

The baseline does not insert domain records.

## Key constraints

Stable keys are required, unique in their domain, trimmed non-empty, and limited
to 120 characters:

```text
family_key
prompt_key
variant_key within one prompt
hook_key
bundle_key
role_key within one bundle revision
```

Human-facing `display_name` values must be non-empty.

Revision numbers must be positive:

```text
ai_prompt_revisions.revision_number > 0
ai_hook_revisions.revision_number > 0
ai_prompt_bundle_revisions.revision_number > 0
```

Allowed variant states:

```text
draft
available
archived
```

Allowed bundle revision states:

```text
draft
published
superseded
```

Publication-state constraints require:

- draft revisions to have `published_at IS NULL`;
- published and superseded revisions to have `published_at IS NOT NULL`;
- `published_at` not to precede `created_at`.

Ordering values are non-negative:

```text
ai_hook_revisions.priority >= 0
ai_prompt_bundle_items.position >= 0
```

Compiled artifacts require:

- one row per bundle revision;
- a globally unique, non-empty content hash;
- a JSON object as `compiled_payload`.

## Foreign keys and ON DELETE decisions

### Prompt family to prompt

```text
ai_prompts.prompt_family_id
-> ai_prompt_families.id
ON DELETE SET NULL
```

A family is optional organizational metadata. Removing it must not delete the
logical prompt. The prompt remains valid without a family.

### Prompt to variant

```text
ai_prompt_variants.prompt_id
-> ai_prompts.id
ON DELETE RESTRICT
```

A prompt with variants cannot be permanently removed. This prevents silent
loss of the variant and revision chain.

### Variant to prompt revision

```text
ai_prompt_revisions.variant_id
-> ai_prompt_variants.id
ON DELETE RESTRICT
```

Prompt revisions are immutable history and must not be removed by deleting a
variant.

### Hook to hook revision

```text
ai_hook_revisions.hook_id
-> ai_hooks.id
ON DELETE RESTRICT
```

Hook revisions are immutable history and must not be removed by deleting a hook
identity.

### Bundle to bundle revision

```text
ai_prompt_bundle_revisions.bundle_id
-> ai_prompt_bundles.id
ON DELETE RESTRICT
```

Bundle revision history must remain explicit and cannot be removed by deleting
the stable bundle identity.

### Bundle revision to bundle item

```text
ai_prompt_bundle_items.bundle_revision_id
-> ai_prompt_bundle_revisions.id
ON DELETE RESTRICT
```

Role mappings are part of bundle revision history. They are not cascade-deleted.

### Prompt revision to bundle item

```text
ai_prompt_bundle_items.prompt_revision_id
-> ai_prompt_revisions.id
ON DELETE RESTRICT
```

An exact prompt revision referenced by a bundle cannot be permanently deleted.
This protects reproducibility.

### Bundle revision to compiled artifact

```text
ai_compiled_bundle_artifacts.bundle_revision_id
-> ai_prompt_bundle_revisions.id
ON DELETE RESTRICT
```

Compiled artifacts are immutable runtime records. Deleting a bundle revision
must not silently remove its artifact.

No v2 domain relation uses `ON DELETE CASCADE`.

## Indexes

Unique constraints create indexes for stable-key and parent-child uniqueness
lookups.

Additional indexes support confirmed access patterns:

| Index | Query pattern |
| --- | --- |
| `ai_prompt_families_active_idx` | List non-deleted families. |
| `ai_prompts_active_idx` | List non-deleted prompts. |
| `ai_prompts_prompt_family_id_idx` | Load prompts in a family. |
| `ai_prompt_variants_active_idx` | Load non-deleted variants for a prompt. |
| `ai_prompt_variants_status_idx` | Filter active variants by status. |
| `ai_hooks_active_idx` | List non-deleted hooks. |
| `ai_prompt_bundles_active_idx` | List non-deleted bundles. |
| `ai_prompt_bundle_revisions_status_idx` | Filter bundle revisions by state. |
| `ai_prompt_bundle_revisions_published_idx` | Find latest published revision. |
| `ai_prompt_bundle_items_order_idx` | Load bundle roles deterministically. |
| `ai_prompt_bundle_items_prompt_revision_id_idx` | Find bundle usage of a prompt revision. |

The unique revision indexes on `(parent_id, revision_number)` support latest
revision lookup through a backward index scan.

## Immutability boundary

Phase 2 establishes immutability through:

- append-oriented revision tables;
- restrictive foreign keys;
- one-artifact-per-revision uniqueness;
- repository modules without update methods for immutable records.

Database triggers are intentionally not added. Later service layers will own
state transitions and publication transactions. Triggers should be introduced
only when a concrete invariant cannot be enforced clearly through constraints
and repository boundaries.

## Transactions

`db.transaction()` performs the following sequence:

```text
open connection
-> open cursor
-> execute caller operations
-> commit on success
-> rollback on exception
-> close cursor and connection
```

The helper supports future multi-step publication work without introducing an
ORM or generic repository framework.

## Transitional HTTP behavior

The Phase 1 UI and compiled-prompt API depend on legacy tables that no longer
exist.

During Phase 2:

- `GET /api/prompts/compiled` returns HTTP `503` and
  `legacy_domain_unavailable`;
- legacy UI routes return a server-rendered HTTP `503` response;
- `GET /healthz` remains operational;
- unknown routes retain normal `404` behavior.

This temporary behavior is removed incrementally when Phase 3 and later v2
routes replace the legacy domain.

## Deferred work

The following remain outside Phase 2:

- family, prompt, variant, and revision CRUD;
- immutable hook-revision creation workflows;
- compiler redesign;
- bundle drafting and publication;
- compiled artifact creation;
- runtime bundle API;
- v2 import and export;
- n8n and `UsingSession/localai` integration changes.
