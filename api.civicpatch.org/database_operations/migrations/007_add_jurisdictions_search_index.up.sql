BEGIN;

CREATE INDEX idx_jurisdictions_data_name_search_pattern
ON jurisdictions (LOWER(data->>'name') text_pattern_ops);

COMMIT;