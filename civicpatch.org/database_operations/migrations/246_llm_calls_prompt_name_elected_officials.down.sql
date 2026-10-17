BEGIN;

UPDATE llm_calls SET prompt_name = 'municipality_officials' WHERE prompt_name = 'elected_officials';

COMMIT;
