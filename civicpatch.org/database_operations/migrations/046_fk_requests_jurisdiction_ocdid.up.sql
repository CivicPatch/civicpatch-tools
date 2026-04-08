BEGIN;

ALTER TABLE requests
    ADD CONSTRAINT fk_requests_jurisdiction_ocdid
    FOREIGN KEY (jurisdiction_ocdid) REFERENCES jurisdictions (jurisdiction_ocdid)
    ON UPDATE CASCADE ON DELETE RESTRICT;

COMMIT;
