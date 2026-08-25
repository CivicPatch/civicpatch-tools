BEGIN;

-- The roster a scrape proposes is derived from its sightings now (`source_records` +
-- `source_record_identities`), so nothing has read this column since the review path moved.
--
-- What goes with it is history, not live data: a published request's roster is in `people`,
-- and a dismissed one's is recoverable from its sightings, which dismissal does not touch.
-- Only requests predating `source_records` lose their proposed roster, and those are already
-- outside the review pool — `AVAILABLE_FOR_REVIEW` requires sightings.
ALTER TABLE requests DROP COLUMN IF EXISTS data_json;

COMMIT;
