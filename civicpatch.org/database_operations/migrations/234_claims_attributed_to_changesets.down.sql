-- Reverses 234: the claims lose the changesets it minted, and those changesets go.

BEGIN;

CREATE TEMP TABLE minted ON COMMIT DROP AS
SELECT id FROM changesets WHERE comment = 'claims filed before every claim had a changeset (234)';

UPDATE claims SET changeset_id = NULL WHERE changeset_id IN (SELECT id FROM minted);
DELETE FROM changesets WHERE id IN (SELECT id FROM minted);

COMMIT;
