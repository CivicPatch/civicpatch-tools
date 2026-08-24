BEGIN;

-- A human accepting or rejecting one field value directly, rather than by editing a row.
--
-- Assertions are current state since 137 — setting a field again overwrites it — so this log is
-- what keeps the superseded value, and the only record of `sources` once it has been replaced.
INSERT INTO change_log_types (type) VALUES ('assert_field');

COMMIT;
