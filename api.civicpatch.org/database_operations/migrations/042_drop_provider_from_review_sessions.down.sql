BEGIN;

ALTER TABLE review_sessions ADD COLUMN provider TEXT;
ALTER TABLE review_sessions ADD COLUMN provider_user_id TEXT;

UPDATE review_sessions rs
    SET provider = u.provider,
        provider_user_id = u.provider_user_id
    FROM users u
    WHERE u.id = rs.user_id;

ALTER TABLE review_sessions ALTER COLUMN provider SET NOT NULL;
ALTER TABLE review_sessions ALTER COLUMN provider_user_id SET NOT NULL;

COMMIT;
