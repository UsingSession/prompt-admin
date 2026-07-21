CREATE TABLE IF NOT EXISTS ai_prompt_hooks (
    hook_key TEXT PRIMARY KEY,
    hook_group TEXT NOT NULL,
    hook_content TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT ai_prompt_hooks_key_not_empty CHECK (length(trim(hook_key)) > 0),
    CONSTRAINT ai_prompt_hooks_group_not_empty CHECK (length(trim(hook_group)) > 0),
    CONSTRAINT ai_prompt_hooks_key_length CHECK (length(hook_key) <= 120),
    CONSTRAINT ai_prompt_hooks_group_length CHECK (length(hook_group) <= 120)
);

CREATE TABLE IF NOT EXISTS ai_prompt_hook_versions (
    id BIGSERIAL PRIMARY KEY,
    hook_key TEXT NOT NULL,
    hook_group TEXT NOT NULL,
    hook_content TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
