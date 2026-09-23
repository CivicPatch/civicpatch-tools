BEGIN;

-- Nothing to undo. The up migration deletes claims, and a deleted claim cannot be restored:
-- its id is what withdraws and rollbacks name it by, so a re-inserted copy would be a
-- different fact wearing the same words.
--
-- Deliberately not an error. `migrate_down` has to reach 220 for the migrations before this
-- one to be reversible, and failing here would block that over rows the application can no
-- longer read or write.

SELECT 1;

COMMIT;
