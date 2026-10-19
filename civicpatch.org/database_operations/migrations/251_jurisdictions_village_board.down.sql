-- A village saved with the form loses it: the form did not exist before.

BEGIN;

UPDATE jurisdictions SET extras_government_form = NULL WHERE extras_government_form = 'village_board';

ALTER TABLE jurisdictions DROP CONSTRAINT IF EXISTS jurisdictions_extras_government_form_check;
ALTER TABLE jurisdictions ADD CONSTRAINT jurisdictions_extras_government_form_check CHECK (
    extras_government_form IS NULL OR extras_government_form IN (
        'mayor_council',
        'council_manager',
        'commission',
        'township_board',
        'open_town_meeting',
        'representative_town_meeting',
        'county_executive'
    )
);

COMMIT;
