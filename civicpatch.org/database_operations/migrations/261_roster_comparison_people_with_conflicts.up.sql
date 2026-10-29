-- Saved rates are snapshots: count people_with_conflicts for runs saved before it existed.

BEGIN;

UPDATE roster_comparison_jurisdictions
SET rates = rates || jsonb_build_object('people_with_conflicts', (
    SELECT count(*)
    FROM roster_comparison_people
    WHERE roster_comparison_people.run_id = roster_comparison_jurisdictions.run_id
      AND roster_comparison_people.jurisdiction_ocdid = roster_comparison_jurisdictions.jurisdiction_ocdid
      AND roster_comparison_people.outcome = 'matched'
      AND EXISTS (
          SELECT 1 FROM jsonb_each(roster_comparison_people.comparison->'fields') AS field
          WHERE field.value->>'level' = 'differs'
      )
));

UPDATE roster_comparison_runs
SET rates = rates || jsonb_build_object('people_with_conflicts', (
    SELECT coalesce(sum((roster_comparison_jurisdictions.rates->>'people_with_conflicts')::int), 0)
    FROM roster_comparison_jurisdictions
    WHERE roster_comparison_jurisdictions.run_id = roster_comparison_runs.id
));

COMMIT;
