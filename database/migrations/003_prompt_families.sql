CREATE TABLE IF NOT EXISTS ai_prompt_families (
    family_key TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT ai_prompt_families_key_not_empty CHECK (length(trim(family_key)) > 0),
    CONSTRAINT ai_prompt_families_key_length CHECK (length(family_key) <= 120)
);

ALTER TABLE ai_system_prompts
ADD COLUMN IF NOT EXISTS prompt_family_key TEXT NULL;

ALTER TABLE ai_system_prompts
ADD COLUMN IF NOT EXISTS family_version INTEGER NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ai_system_prompts_family_complete'
    ) THEN
        ALTER TABLE ai_system_prompts
        ADD CONSTRAINT ai_system_prompts_family_complete CHECK (
            (prompt_family_key IS NULL AND family_version IS NULL)
            OR (prompt_family_key IS NOT NULL AND family_version IS NOT NULL)
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ai_system_prompts_family_version_positive'
    ) THEN
        ALTER TABLE ai_system_prompts
        ADD CONSTRAINT ai_system_prompts_family_version_positive CHECK (
            family_version IS NULL OR family_version > 0
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ai_system_prompts_family_fk'
    ) THEN
        ALTER TABLE ai_system_prompts
        ADD CONSTRAINT ai_system_prompts_family_fk
        FOREIGN KEY (prompt_family_key)
        REFERENCES ai_prompt_families(family_key);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS ai_system_prompts_family_version_unique
ON ai_system_prompts(prompt_family_key, family_version)
WHERE prompt_family_key IS NOT NULL;
