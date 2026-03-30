BEGIN;

ALTER TABLE requests
    DROP CONSTRAINT fk_requests_jurisdiction_ocdid;

COMMIT;
