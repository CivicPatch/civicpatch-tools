BEGIN;

DELETE FROM review_issues WHERE issue_type = 'excluded_person';

COMMIT;
