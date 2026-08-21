BEGIN;

-- One type for both outcomes. A seat and a move differ only in whether the person already
-- held something in this body, and `moved_from` in the payload says which — the same rule
-- the role events follow, where kind lives in the payload rather than the type.
INSERT INTO change_log_types (type) VALUES ('assign_membership');

COMMIT;
