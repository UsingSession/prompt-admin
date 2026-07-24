# Hook Compiler

## Placeholder grammar

The compiler recognizes exact Hook placeholder tokens using:

```text
#hook_[A-Za-z0-9_.-]+
```

The database and API store the group without the leading `#`.

The parser scans left to right, returns groups in first-occurrence order, and
deduplicates the detected-group metadata list. Every recognized occurrence is
replaced. Prompt text outside recognized placeholders is not modified.

`_vN` text is part of a group name. It is never interpreted as a Revision
selector.

## Effective Hook Revision

The effective Revision for one Hook is always:

```text
the Revision with the highest revision_number
```

There is no mutable current-Revision pointer and no fallback to an older enabled
Revision.

Consequences:

- a Hook without Revisions contributes nothing;
- a disabled latest Revision disables the Hook contribution;
- a newer enabled Revision re-enables the Hook;
- a deleted Hook contributes nothing;
- restoring a Hook reuses its latest Revision and `is_enabled` state.

## Deterministic resolution

All detected groups are resolved with one repository query.

For each group, the compiler:

1. considers non-deleted Hooks;
2. selects each Hook's highest Revision number;
3. includes only enabled latest Revisions in the requested group;
4. orders contributors by `priority ASC`, then `hook_key ASC`;
5. joins Hook content with `\n\n`.

Database IDs, timestamps, insertion order, and query-plan order do not affect
compiled output.

## Transaction compatibility

The compiler is split into:

```text
parse placeholders
-> pure operation

load effective Hook Revisions
-> repository operation using a caller-provided cursor

compile resolved content
-> pure operation
```

`compile_with_cursor()` never opens an independent database connection. Future
Bundle publication can call it inside the publication transaction.

## Preview mode

Preview mode is read-only and diagnostic.

It returns a result when groups are unresolved, preserves unresolved placeholder
tokens, and reports detected groups, resolved Hook metadata, and unresolved
groups.

Prompt Revision preview endpoint:

```http
GET /api/v1/prompts/{prompt_key}/variants/{variant_key}/revisions/
    {revision}/compiled-preview
```

The endpoint loads the exact immutable Prompt Revision and compiles it against
current effective Hook Revisions.

The preview can change after Hook Revision creation, enable or disable changes,
Hook soft deletion, or restoration. It is therefore not a reproducible runtime
artifact, published Bundle, or n8n production contract.

## Strict mode

Strict mode uses the same parser and deterministic resolution. It fails when
any group is unresolved:

```text
unresolved_hook_groups
```

It does not return a successful partial compilation and performs no writes.
Phase 5 Bundle publication will consume this service contract.

## Result model

```json
{
  "mode": "preview",
  "raw_prompt": "Follow these rules:\n\n#hook_global.response_rules",
  "compiled_prompt": "Follow these rules:\n\nResolved content",
  "detected_groups": [
    "hook_global.response_rules"
  ],
  "resolved_hooks": [
    {
      "hook_key": "global.response.no_markdown",
      "revision_number": 3,
      "hook_group": "hook_global.response_rules",
      "priority": 100
    }
  ],
  "unresolved_groups": []
}
```

`raw_prompt` remains unchanged. Internal IDs, SQL rows, and Hook content metadata
are not exposed beyond the compiled text and documented response fields.

## Publication boundary

Phase 4A does not calculate a content hash, create a Bundle, publish an artifact,
or expose the final runtime Bundle API. Hashing belongs to immutable Bundle
publication.
