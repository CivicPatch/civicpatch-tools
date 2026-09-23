BEGIN;

-- "Not a member of anything here" was removed 2026-09-23: nothing wrote it any more, and
-- nothing had read it since the fold replaced `close_for_people_rejected_here`. These rows are
-- the claims it left, and `field_path = 'exists'` on a person is now a shape the model has no
-- name for.
--
-- Migration 217 already converted the ones that meant something: §1 turned the membership-level
-- existence claims into `posts` claims, and §3 turned each person-level reject into a withdrawal
-- of the source records behind it. So what this deletes is the residue of that conversion, not
-- anybody's answer.
--
-- Irreversible. The down file cannot restore a deleted claim, and says so. Withdrawing them
-- instead would keep the rows, but a withdraw is itself a claim about a fact, and these are
-- facts in a vocabulary nothing speaks: the honest cleanup is that they stop existing.
--
-- Rerunnable: the second pass matches nothing.

DELETE FROM assertions
 WHERE entity_type = 'person'
   AND field_path = 'exists';

-- The withdraw rows that pointed at them, which now name nothing. `entity_type = 'claim'` is a
-- withdraw's way of naming a fact by row id, so an orphan is unreachable rather than merely
-- unread.
DELETE FROM assertions w
 WHERE w.kind = 'withdraw'
   AND w.entity_type = 'claim'
   AND NOT EXISTS (SELECT 1 FROM assertions target WHERE target.id = w.entity_id);

COMMIT;
