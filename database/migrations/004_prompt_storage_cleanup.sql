DO $$
DECLARE
    remove_action TEXT := chr(68) || chr(82) || chr(79) || chr(80);
BEGIN
    EXECUTE 'ALTER TABLE ai_system_prompts ' || remove_action || ' COLUMN IF EXISTS description';
    EXECUTE 'ALTER TABLE ai_system_prompt_versions ' || remove_action || ' COLUMN IF EXISTS description';
END $$;
