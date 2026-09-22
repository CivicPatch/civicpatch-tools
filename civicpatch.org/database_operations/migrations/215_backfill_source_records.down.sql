BEGIN;

-- Records and identities cascade from their changeset.
DELETE FROM changesets
 WHERE kind = 'sheet_import'
   AND comment = 'migration 215: roster loaded before source records existed';

COMMIT;
