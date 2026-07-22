CREATE TABLE IF NOT EXISTS prompt_admin_migrations (
    migration_name TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
