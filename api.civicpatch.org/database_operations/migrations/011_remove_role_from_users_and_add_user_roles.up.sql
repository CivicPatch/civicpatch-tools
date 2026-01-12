BEGIN;

ALTER TABLE users
    DROP COLUMN role;

CREATE TABLE user_roles (
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    PRIMARY KEY (provider, provider_user_id, role),
    FOREIGN KEY (provider, provider_user_id)
        REFERENCES users(provider, provider_user_id)
        ON DELETE CASCADE
);

COMMIT;