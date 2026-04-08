BEGIN;

ALTER TABLE review_sessions DROP COLUMN session_date CASCADE;

ALTER TABLE review_sessions
    ADD COLUMN user_id UUID REFERENCES users(id);

UPDATE review_sessions rs
    SET user_id = u.id
    FROM users u
    WHERE u.provider = rs.provider
      AND u.provider_user_id = rs.provider_user_id;

ALTER TABLE review_sessions
    ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE review_sessions
    ADD CONSTRAINT review_sessions_user_state_unique
    UNIQUE (user_id, state_code);

COMMIT;
