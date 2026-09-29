-- The open-data entry's fields as their own columns, written by the sync beside `data` and
-- filled here once from it. Readers still use `data`; moving them and dropping `data` is a
-- later cleanup. `extras_government_form` is the entry's `extras.government_form`, which
-- replaces cp.org's own `meta_government_form`: a rule-decided form is derived, never saved.

BEGIN;

ALTER TABLE jurisdictions DROP CONSTRAINT IF EXISTS jurisdictions_meta_government_form_check;
ALTER TABLE jurisdictions DROP COLUMN IF EXISTS meta_government_form;

ALTER TABLE jurisdictions
    ADD COLUMN IF NOT EXISTS name text,
    ADD COLUMN IF NOT EXISTS url text,
    ADD COLUMN IF NOT EXISTS population integer,
    ADD COLUMN IF NOT EXISTS geoid text,
    ADD COLUMN IF NOT EXISTS wiki_url text,
    ADD COLUMN IF NOT EXISTS extras_government_form text;

UPDATE jurisdictions
SET name = data->>'name',
    url = data->>'url',
    population = (data->>'population')::integer,
    geoid = data->>'geoid',
    wiki_url = data->>'wiki_url',
    extras_government_form = data->'extras'->>'government_form';

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
