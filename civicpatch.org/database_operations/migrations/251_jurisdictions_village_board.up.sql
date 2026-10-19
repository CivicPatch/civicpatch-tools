-- village_board: a state's own government form (Vermont's and Michigan's statutory villages),
-- defined in that state's config file, not the country's. Mirrors GovernmentForm.

BEGIN;

ALTER TABLE jurisdictions DROP CONSTRAINT IF EXISTS jurisdictions_extras_government_form_check;
ALTER TABLE jurisdictions ADD CONSTRAINT jurisdictions_extras_government_form_check CHECK (
    extras_government_form IS NULL OR extras_government_form IN (
        'mayor_council',
        'council_manager',
        'commission',
        'township_board',
        'open_town_meeting',
        'representative_town_meeting',
        'county_executive',
        'village_board'
    )
);

COMMIT;
