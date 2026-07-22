CREATE TABLE ai_prompt_families (
    id BIGSERIAL PRIMARY KEY,
    family_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT ai_prompt_families_family_key_unique UNIQUE (family_key),
    CONSTRAINT ai_prompt_families_family_key_not_empty
        CHECK (length(trim(family_key)) > 0),
    CONSTRAINT ai_prompt_families_family_key_length
        CHECK (length(family_key) <= 120),
    CONSTRAINT ai_prompt_families_display_name_not_empty
        CHECK (length(trim(display_name)) > 0)
);

CREATE TABLE ai_prompts (
    id BIGSERIAL PRIMARY KEY,
    prompt_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    prompt_family_id BIGINT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT ai_prompts_prompt_key_unique UNIQUE (prompt_key),
    CONSTRAINT ai_prompts_prompt_key_not_empty
        CHECK (length(trim(prompt_key)) > 0),
    CONSTRAINT ai_prompts_prompt_key_length
        CHECK (length(prompt_key) <= 120),
    CONSTRAINT ai_prompts_display_name_not_empty
        CHECK (length(trim(display_name)) > 0),
    CONSTRAINT ai_prompts_prompt_family_fk
        FOREIGN KEY (prompt_family_id)
        REFERENCES ai_prompt_families(id)
        ON DELETE SET NULL
);

CREATE TABLE ai_prompt_variants (
    id BIGSERIAL PRIMARY KEY,
    prompt_id BIGINT NOT NULL,
    variant_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT ai_prompt_variants_prompt_variant_unique
        UNIQUE (prompt_id, variant_key),
    CONSTRAINT ai_prompt_variants_variant_key_not_empty
        CHECK (length(trim(variant_key)) > 0),
    CONSTRAINT ai_prompt_variants_variant_key_length
        CHECK (length(variant_key) <= 120),
    CONSTRAINT ai_prompt_variants_display_name_not_empty
        CHECK (length(trim(display_name)) > 0),
    CONSTRAINT ai_prompt_variants_status_allowed
        CHECK (status IN ('draft', 'available', 'archived')),
    CONSTRAINT ai_prompt_variants_prompt_fk
        FOREIGN KEY (prompt_id)
        REFERENCES ai_prompts(id)
        ON DELETE RESTRICT
);

CREATE TABLE ai_prompt_revisions (
    id BIGSERIAL PRIMARY KEY,
    variant_id BIGINT NOT NULL,
    revision_number INTEGER NOT NULL,
    system_prompt TEXT NOT NULL,
    change_note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ai_prompt_revisions_variant_revision_unique
        UNIQUE (variant_id, revision_number),
    CONSTRAINT ai_prompt_revisions_revision_number_positive
        CHECK (revision_number > 0),
    CONSTRAINT ai_prompt_revisions_variant_fk
        FOREIGN KEY (variant_id)
        REFERENCES ai_prompt_variants(id)
        ON DELETE RESTRICT
);

CREATE TABLE ai_hooks (
    id BIGSERIAL PRIMARY KEY,
    hook_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT ai_hooks_hook_key_unique UNIQUE (hook_key),
    CONSTRAINT ai_hooks_hook_key_not_empty
        CHECK (length(trim(hook_key)) > 0),
    CONSTRAINT ai_hooks_hook_key_length
        CHECK (length(hook_key) <= 120),
    CONSTRAINT ai_hooks_display_name_not_empty
        CHECK (length(trim(display_name)) > 0)
);

CREATE TABLE ai_hook_revisions (
    id BIGSERIAL PRIMARY KEY,
    hook_id BIGINT NOT NULL,
    revision_number INTEGER NOT NULL,
    hook_group TEXT NOT NULL,
    hook_content TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    change_note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ai_hook_revisions_hook_revision_unique
        UNIQUE (hook_id, revision_number),
    CONSTRAINT ai_hook_revisions_revision_number_positive
        CHECK (revision_number > 0),
    CONSTRAINT ai_hook_revisions_hook_group_not_empty
        CHECK (length(trim(hook_group)) > 0),
    CONSTRAINT ai_hook_revisions_hook_group_length
        CHECK (length(hook_group) <= 120),
    CONSTRAINT ai_hook_revisions_priority_non_negative
        CHECK (priority >= 0),
    CONSTRAINT ai_hook_revisions_hook_fk
        FOREIGN KEY (hook_id)
        REFERENCES ai_hooks(id)
        ON DELETE RESTRICT
);

CREATE TABLE ai_prompt_bundles (
    id BIGSERIAL PRIMARY KEY,
    bundle_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT ai_prompt_bundles_bundle_key_unique UNIQUE (bundle_key),
    CONSTRAINT ai_prompt_bundles_bundle_key_not_empty
        CHECK (length(trim(bundle_key)) > 0),
    CONSTRAINT ai_prompt_bundles_bundle_key_length
        CHECK (length(bundle_key) <= 120),
    CONSTRAINT ai_prompt_bundles_display_name_not_empty
        CHECK (length(trim(display_name)) > 0)
);

CREATE TABLE ai_prompt_bundle_revisions (
    id BIGSERIAL PRIMARY KEY,
    bundle_id BIGINT NOT NULL,
    revision_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    change_note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ NULL,
    CONSTRAINT ai_prompt_bundle_revisions_bundle_revision_unique
        UNIQUE (bundle_id, revision_number),
    CONSTRAINT ai_prompt_bundle_revisions_revision_number_positive
        CHECK (revision_number > 0),
    CONSTRAINT ai_prompt_bundle_revisions_status_allowed
        CHECK (status IN ('draft', 'published', 'superseded')),
    CONSTRAINT ai_prompt_bundle_revisions_publication_state_valid
        CHECK (
            (status = 'draft' AND published_at IS NULL)
            OR (
                status IN ('published', 'superseded')
                AND published_at IS NOT NULL
            )
        ),
    CONSTRAINT ai_prompt_bundle_revisions_published_at_valid
        CHECK (published_at IS NULL OR published_at >= created_at),
    CONSTRAINT ai_prompt_bundle_revisions_bundle_fk
        FOREIGN KEY (bundle_id)
        REFERENCES ai_prompt_bundles(id)
        ON DELETE RESTRICT
);

CREATE TABLE ai_prompt_bundle_items (
    id BIGSERIAL PRIMARY KEY,
    bundle_revision_id BIGINT NOT NULL,
    role_key TEXT NOT NULL,
    prompt_revision_id BIGINT NOT NULL,
    position INTEGER NOT NULL DEFAULT 100,
    CONSTRAINT ai_prompt_bundle_items_revision_role_unique
        UNIQUE (bundle_revision_id, role_key),
    CONSTRAINT ai_prompt_bundle_items_role_key_not_empty
        CHECK (length(trim(role_key)) > 0),
    CONSTRAINT ai_prompt_bundle_items_role_key_length
        CHECK (length(role_key) <= 120),
    CONSTRAINT ai_prompt_bundle_items_position_non_negative
        CHECK (position >= 0),
    CONSTRAINT ai_prompt_bundle_items_bundle_revision_fk
        FOREIGN KEY (bundle_revision_id)
        REFERENCES ai_prompt_bundle_revisions(id)
        ON DELETE RESTRICT,
    CONSTRAINT ai_prompt_bundle_items_prompt_revision_fk
        FOREIGN KEY (prompt_revision_id)
        REFERENCES ai_prompt_revisions(id)
        ON DELETE RESTRICT
);

CREATE TABLE ai_compiled_bundle_artifacts (
    id BIGSERIAL PRIMARY KEY,
    bundle_revision_id BIGINT NOT NULL,
    content_hash TEXT NOT NULL,
    compiled_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ai_compiled_bundle_artifacts_revision_unique
        UNIQUE (bundle_revision_id),
    CONSTRAINT ai_compiled_bundle_artifacts_content_hash_unique
        UNIQUE (content_hash),
    CONSTRAINT ai_compiled_bundle_artifacts_content_hash_not_empty
        CHECK (length(trim(content_hash)) > 0),
    CONSTRAINT ai_compiled_bundle_artifacts_payload_object
        CHECK (jsonb_typeof(compiled_payload) = 'object'),
    CONSTRAINT ai_compiled_bundle_artifacts_bundle_revision_fk
        FOREIGN KEY (bundle_revision_id)
        REFERENCES ai_prompt_bundle_revisions(id)
        ON DELETE RESTRICT
);

CREATE INDEX ai_prompt_families_active_idx
    ON ai_prompt_families(id)
    WHERE deleted_at IS NULL;

CREATE INDEX ai_prompts_active_idx
    ON ai_prompts(id)
    WHERE deleted_at IS NULL;

CREATE INDEX ai_prompts_prompt_family_id_idx
    ON ai_prompts(prompt_family_id)
    WHERE prompt_family_id IS NOT NULL;

CREATE INDEX ai_prompt_variants_active_idx
    ON ai_prompt_variants(prompt_id, id)
    WHERE deleted_at IS NULL;

CREATE INDEX ai_prompt_variants_status_idx
    ON ai_prompt_variants(status, prompt_id)
    WHERE deleted_at IS NULL;

CREATE INDEX ai_hooks_active_idx
    ON ai_hooks(id)
    WHERE deleted_at IS NULL;

CREATE INDEX ai_prompt_bundles_active_idx
    ON ai_prompt_bundles(id)
    WHERE deleted_at IS NULL;

CREATE INDEX ai_prompt_bundle_revisions_status_idx
    ON ai_prompt_bundle_revisions(bundle_id, status, revision_number DESC);

CREATE INDEX ai_prompt_bundle_revisions_published_idx
    ON ai_prompt_bundle_revisions(bundle_id, revision_number DESC)
    WHERE status = 'published';

CREATE INDEX ai_prompt_bundle_items_order_idx
    ON ai_prompt_bundle_items(bundle_revision_id, position, role_key);

CREATE INDEX ai_prompt_bundle_items_prompt_revision_id_idx
    ON ai_prompt_bundle_items(prompt_revision_id);
