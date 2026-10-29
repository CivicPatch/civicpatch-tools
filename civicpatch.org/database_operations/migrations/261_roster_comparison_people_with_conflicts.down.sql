BEGIN;

UPDATE roster_comparison_jurisdictions SET rates = rates - 'people_with_conflicts';
UPDATE roster_comparison_runs SET rates = rates - 'people_with_conflicts';

COMMIT;
