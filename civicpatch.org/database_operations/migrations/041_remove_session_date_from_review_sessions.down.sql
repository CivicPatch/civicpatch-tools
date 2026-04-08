BEGIN;

ALTER TABLE review_sessions
    DROP CONSTRAINT review_sessions_user_state_unique;

ALTER TABLE review_sessions
    DROP COLUMN user_id;

ALTER TABLE review_sessions
    ADD COLUMN session_date DATE;

UPDATE review_sessions
    SET session_date = (created_at AT TIME ZONE 'America/Los_Angeles')::date;

ALTER TABLE review_sessions
    ALTER COLUMN session_date SET NOT NULL,
    ALTER COLUMN session_date SET DEFAULT CURRENT_DATE;

ALTER TABLE review_sessions
    ADD CONSTRAINT review_sessions_provider_provider_user_id_session_date_state_unique
    UNIQUE (provider, provider_user_id, session_date, state_code);

COMMIT;
