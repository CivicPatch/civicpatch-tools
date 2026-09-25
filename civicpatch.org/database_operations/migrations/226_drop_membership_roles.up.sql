-- Nothing read membership_roles but the projection diff checking it against itself. The extra
-- roles a label names stay in the fold, which parses them from the verbatim label (step 10a).

BEGIN;

DROP TABLE IF EXISTS membership_roles;

COMMIT;
