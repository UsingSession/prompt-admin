# Prompt Admin

Prompt Admin is a lightweight local admin UI and runtime prompt provider for
managing LLM system prompts, prompt families, and reusable prompt hooks stored
in PostgreSQL.

It is a generic prompt-management service. It does not ship with domain-specific
prompts, and it does not assume any specific use case such as image generation,
content generation, coding assistance, or agent routing.

## Purpose

Prompt Admin exists to make prompt management editable from a browser without
opening workflow tools or editing Markdown files manually.

The current source of truth is PostgreSQL:

```text
Prompt Admin UI -> PostgreSQL -> Prompt Admin API -> runtime consumer
```

Runtime consumers such as n8n workflows should load compiled prompts from the
Prompt Admin API instead of querying PostgreSQL directly. This keeps hook
resolution inside Prompt Admin.

## Local URL

After starting the service, open:

```text
http://localhost:8090
```

Health check:

```text
http://localhost:8090/healthz
```

The service is intended for local use only. It has no authentication. When it
is published through Docker Compose, bind it to `127.0.0.1` and do not expose it
publicly.

## Design constraints

Prompt Admin is intentionally small and dependency-light.

Current design:

- Python stdlib HTTP server.
- PostgreSQL access through `psycopg`.
- Server-rendered HTML templates.
- Plain CSS.
- SQL migrations.
- No Flask.
- No FastAPI.
- No ORM.
- No frontend framework.
- No separate auth layer.

`app.py` remains only the server entrypoint. Most logic is split into smaller
modules.

## Main features

### Prompt management

Prompt Admin supports:

- listing prompts;
- filtering prompts by category, status, and search text;
- creating prompts;
- editing prompts;
- prompt family assignment;
- active/inactive state;
- validation warnings;
- compiled prompt preview;
- compiled prompts API;
- clone as new family item;
- soft delete;
- restore;
- permanent delete;
- version history;
- Markdown/text download;
- JSON export/import.

Prompt fields:

| Field | Purpose |
| --- | --- |
| `prompt_key` | Stable identifier used by runtime consumers. |
| `system_prompt` | Raw prompt text with optional hook placeholders. This is the source of truth for prompt behavior. |
| `category` | Optional UI grouping and API filter. |
| `prompt_family_key` | Optional logical family/group relation. |
| `family_version` | Internal family item number. In the UI this is shown as `Family item #`, not as a revision. |
| `is_active` | Whether the prompt is active and available through the runtime API. |
| `created_at` | Creation timestamp. |
| `updated_at` | Last update timestamp. |
| `deleted_at` | Soft-delete timestamp. |

Prompt-level `description` is intentionally not used. The `system_prompt`
textarea should explain what the prompt does.

### Prompt families

Prompt families are logical groups of related but independent prompts.

```text
Family = logical group / collection
Family item = one independent prompt inside that group
Family is not a revision chain
```

Family fields:

| Field | Purpose |
| --- | --- |
| `family_key` | Stable identifier of the prompt family. |
| `description` | Human-facing note about the group. Not sent to the LLM. |
| `created_at` | Creation timestamp. |
| `updated_at` | Last update timestamp. |
| `deleted_at` | Soft-delete timestamp. |

Family routes:

```text
/families
/families?q=<query>
/family?key=<family_key>
/family-new
/family-edit?key=<family_key>
/family-confirm-delete?key=<family_key>
```

Family overview shows attached prompts with:

- family item number;
- prompt key;
- category;
- active/inactive state;
- updated date;
- actions: Edit, Preview, Clone as new family item.

Deleting a family is blocked while prompts still reference it. Detach or delete
attached prompts first.

### Prompt hooks

Prompt hooks are reusable rule blocks that can be inserted into prompts with
placeholders.

Example prompt:

```text
You are a local assistant.

#hook_global_rules

Return only valid JSON.
```

Example hook group:

```text
hook_global_rules
```

All active hooks from the matching group are inserted into the compiled prompt,
ordered by priority.

Hook fields:

| Field | Purpose |
| --- | --- |
| `hook_key` | Stable identifier of one hook record. |
| `hook_group` | Group matched by placeholders such as `#hook_global_rules`. |
| `hook_content` | Reusable text inserted into compiled prompts. |
| `description` | Human-readable note. Not inserted into the prompt. |
| `category` | Optional UI grouping. |
| `priority` | Lower values are inserted first inside the same group. |
| `is_active` | Whether the hook is eligible for compilation. |
| `created_at` | Creation timestamp. |
| `updated_at` | Last update timestamp. |
| `deleted_at` | Soft-delete timestamp. |

### Hook group input

The hook form shows `hook_` as a visual prefix.

User input:

```text
global_rules
```

Stored value:

```text
hook_global_rules
```

Prompt placeholder:

```text
#hook_global_rules
```

If a full value such as `hook_global_rules` is entered, it is kept as-is and is
not converted to `hook_hook_global_rules`.

### Compiled prompt preview

The preview page shows what will be sent to the runtime consumer after hook
placeholders are resolved.

Preview includes:

- raw prompt;
- detected hook groups;
- resolved hooks;
- unresolved hook groups;
- compiled prompt.

URL pattern:

```text
/preview?key=<prompt_key>
```

### Compiled prompts API

Prompt Admin exposes a JSON endpoint for runtime usage:

```text
GET /api/prompts/compiled
```

Use this endpoint instead of direct PostgreSQL prompt queries from external
workflow tools. The endpoint returns active prompts with hooks already inserted.

Internal Docker URL example:

```text
http://prompt-admin:8090/api/prompts/compiled
```

Host URL for browser testing:

```text
http://localhost:8090/api/prompts/compiled
```

The endpoint requires at least one selector:

- `category`
- `key`
- `keys`

Load all active prompts from a category:

```text
GET http://prompt-admin:8090/api/prompts/compiled?category=general
```

Load multiple prompts by repeated `key` parameters:

```text
GET http://prompt-admin:8090/api/prompts/compiled?key=assistant_rules&key=response_formatter
```

Load multiple prompts by comma-separated `keys`:

```text
GET http://prompt-admin:8090/api/prompts/compiled?keys=assistant_rules,response_formatter
```

Combine category and keys:

```text
GET http://prompt-admin:8090/api/prompts/compiled?category=general&keys=assistant_rules,response_formatter
```

When both category and keys are provided, the response contains the
intersection: active prompts in that category and matching the requested keys.

When keys are requested, `missing_keys` lists requested keys that were not
returned. This can happen when a prompt does not exist, is inactive, is
soft-deleted, or is excluded by the category filter. For category-only requests,
`missing_keys` is an empty array.

Response shape:

```json
{
  "category": "general",
  "keys": ["assistant_rules"],
  "missing_keys": [],
  "count": 1,
  "prompts": [
    {
      "prompt_key": "assistant_rules",
      "category": "general",
      "is_active": true,
      "updated_at": "2026-07-01T06:00:00+00:00",
      "raw_prompt": "Raw prompt with #hook_global_rules",
      "compiled_prompt": "Prompt with hooks inserted",
      "detected_groups": ["hook_global_rules"],
      "resolved_hooks": [
        {
          "hook_key": "hook_global_rules-user_intent",
          "hook_group": "hook_global_rules",
          "description": "User intent preservation rule",
          "category": "global",
          "priority": 10,
          "is_active": true
        }
      ],
      "unresolved_groups": []
    }
  ]
}
```

The main runtime field is:

```text
compiled_prompt
```

Example mapping code for a workflow tool after the HTTP Request step:

```js
const promptMap = {};

for (const prompt of $json.prompts || []) {
  promptMap[prompt.prompt_key] = prompt.compiled_prompt;
}

return [
  {
    json: {
      ...$json,
      prompt_map: promptMap,
    },
  }
];
```

Then use a compiled prompt in later workflow steps:

```text
{{$json.prompt_map.assistant_rules}}
```

API help page in the UI:

```text
/api-docs
```

### Clone flow

Prompts and hooks can be cloned.

Prompt clone behavior:

- opens a copied form;
- does not save immediately;
- creates a new family item;
- generates the next available prompt key for grouped prompts;
- preserves the source prompt as an independent prompt.

Hook clone behavior:

- opens a copied form;
- does not save immediately;
- allows editing the key, group, and all other fields.

### Delete lifecycle

Prompt Admin uses a two-step delete model.

```text
Delete              -> soft delete, moves the record to Deleted Records
Restore             -> restores the soft-deleted record
Delete permanently  -> removes the record and its version history
```

Permanent delete is only available from the deleted records page.

This avoids accidentally hard-deleting active prompts, families, or hooks.

### Import/export

Export returns prompts, families, and hooks:

```json
{
  "families": [],
  "prompts": [],
  "hooks": []
}
```

Import supports the same structure and has a preview/apply flow.

Prompt import validates `prompt_family_key` and `family_version` as a pair. If
one is provided, the other must also be provided, and `family_version` must be a
positive integer.

Useful URLs:

```text
/export
/import
```

## Startup behavior

Prompt Admin initializes database schema and applies SQL migrations during
startup.

It does not create starter prompts or domain-specific prompt records. A fresh
database starts empty except for schema and migration metadata. Prompts, hooks,
and families should be created through the UI or imported from JSON.

## Database model

Prompt Admin uses these main tables:

| Table | Purpose |
| --- | --- |
| `ai_prompt_families` | Prompt family records. |
| `ai_system_prompts` | Current prompt records. |
| `ai_system_prompt_versions` | Prompt version history snapshots. |
| `ai_prompt_hooks` | Current hook records. |
| `ai_prompt_hook_versions` | Hook version history. |
| `prompt_admin_migrations` | Applied migration tracking. |

Schema and migrations live in:

```text
prompt-admin/database/
├─ schema.sql
└─ migrations/
   ├─ 001_prompt_admin_metadata.sql
   ├─ 002_prompt_hooks.sql
   ├─ 003_prompt_families.sql
   └─ 004_prompt_storage_cleanup.sql
```

## File structure

```text
prompt-admin/
├─ app.py                  # Server entrypoint
├─ config.py               # Environment and paths
├─ db.py                   # Database connection and initialization
├─ repository.py           # Prompt persistence
├─ hook_repository.py      # Hook persistence
├─ compiler.py             # Hook placeholder resolution
├─ handlers.py             # HTTP routes
├─ render.py               # Template rendering helpers
├─ validation.py           # Key/text validation helpers
├─ exporting.py            # Import/export helpers
├─ static_files.py         # Static file serving
├─ database/
├─ static/
├─ templates/
└─ tests/
```

## Important routes

| Route | Purpose |
| --- | --- |
| `/` | Prompt list. |
| `/new` | Create prompt form. |
| `/edit?key=<prompt_key>` | Edit prompt. |
| `/clone?key=<prompt_key>` | Clone prompt as a new family item. |
| `/preview?key=<prompt_key>` | Compiled prompt preview. |
| `/history?key=<prompt_key>` | Prompt version history. |
| `/families` | Prompt family list. |
| `/family?key=<family_key>` | Prompt family overview. |
| `/family-new` | Create family form. |
| `/family-edit?key=<family_key>` | Edit family. |
| `/api-docs` | HTML help page for runtime API usage. |
| `/api/prompts/compiled` | JSON endpoint for compiled prompts. |
| `/hooks` | Hook list. |
| `/hook-new` | Create hook form. |
| `/hook-edit?key=<hook_key>` | Edit hook. |
| `/hook-clone?key=<hook_key>` | Clone hook. |
| `/hook-history?key=<hook_key>` | Hook version history. |
| `/deleted` | Soft-deleted prompts, families, and hooks. |
| `/import` | Import JSON. |
| `/export` | Export JSON. |
| `/healthz` | Service/database health check. |

## Local verification

Run unit tests from the repository root:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Build the Docker image:

```bash
docker build -t prompt-admin:local .
```

Manual pages to check after starting the service:

```text
http://localhost:8090/
http://localhost:8090/families
http://localhost:8090/family?key=<family_key>
http://localhost:8090/hooks
http://localhost:8090/api-docs
http://localhost:8090/hook-new
http://localhost:8090/preview?key=<prompt_key>
http://localhost:8090/api/prompts/compiled?category=general
http://localhost:8090/api/prompts/compiled?keys=assistant_rules,response_formatter
http://localhost:8090/deleted
http://localhost:8090/import
http://localhost:8090/export
http://localhost:8090/healthz
```

## Operational notes

- Prompt Admin is local-only.
- It has no user authentication.
- PostgreSQL is the source of truth for prompts, families, and hooks.
- Runtime consumers should use the compiled prompts API instead of direct
  PostgreSQL prompt queries.
- Markdown files are not the primary prompt storage model.
- The application does not create default prompts during startup.
- Backups should include the PostgreSQL dump.
