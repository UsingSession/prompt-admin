CREATE TABLE IF NOT EXISTS ai_prompt_families (
    family_key TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT ai_prompt_families_key_not_empty CHECK (length(trim(family_key)) > 0),
    CONSTRAINT ai_prompt_families_key_length CHECK (length(family_key) <= 120)
);

CREATE TABLE IF NOT EXISTS ai_system_prompts (
    prompt_key TEXT PRIMARY KEY,
    system_prompt TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    prompt_family_key TEXT NULL,
    family_version INTEGER NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT ai_system_prompts_key_not_empty CHECK (length(trim(prompt_key)) > 0),
    CONSTRAINT ai_system_prompts_key_length CHECK (length(prompt_key) <= 120),
    CONSTRAINT ai_system_prompts_family_complete CHECK (
        (prompt_family_key IS NULL AND family_version IS NULL)
        OR (prompt_family_key IS NOT NULL AND family_version IS NOT NULL)
    ),
    CONSTRAINT ai_system_prompts_family_version_positive CHECK (family_version IS NULL OR family_version > 0),
    CONSTRAINT ai_system_prompts_family_fk FOREIGN KEY (prompt_family_key) REFERENCES ai_prompt_families(family_key)
);

ALTER TABLE ai_system_prompts
ADD COLUMN IF NOT EXISTS prompt_family_key TEXT NULL;

ALTER TABLE ai_system_prompts
ADD COLUMN IF NOT EXISTS family_version INTEGER NULL;

ALTER TABLE ai_system_prompts
DROP COLUMN IF EXISTS description;

CREATE UNIQUE INDEX IF NOT EXISTS ai_system_prompts_family_version_unique
ON ai_system_prompts(prompt_family_key, family_version)
WHERE prompt_family_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS ai_system_prompt_versions (
    id BIGSERIAL PRIMARY KEY,
    prompt_key TEXT NOT NULL,
    system_prompt TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE ai_system_prompt_versions
DROP COLUMN IF EXISTS description;

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

CREATE TABLE IF NOT EXISTS prompt_admin_migrations (
    migration_name TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
