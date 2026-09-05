BEGIN;

UPDATE issues SET issue_type = 'no_info' WHERE issue_type = 'no_roster_found';

COMMIT;
