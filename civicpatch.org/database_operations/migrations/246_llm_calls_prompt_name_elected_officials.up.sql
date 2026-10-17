-- The officials prompt runs on counties too, not only municipalities. Renamed so its history
-- stays one key: the evals and spend queries group by prompt_name.

BEGIN;

UPDATE llm_calls SET prompt_name = 'elected_officials' WHERE prompt_name = 'municipality_officials';

COMMIT;
