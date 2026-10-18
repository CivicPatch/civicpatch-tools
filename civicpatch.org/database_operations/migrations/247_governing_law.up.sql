-- What law governs a jurisdiction, as the governing_law_collector last found it: cp.org's own
-- column beside extras_government_form (extras_: a fact about the jurisdiction the OCD schema has no field for), never written by the open-data sync. Its shape is
-- shared.schemas.GoverningLaw; it points at governing_law_source_pages rows by id.
--
-- governing_law_source_pages is the collector's own page table, apart from source_pages (the
-- people scrape's), whose run, changeset and relevance columns mean nothing here. The text is
-- markdown in the artifacts bucket at cache_path, content-addressed (governing_law/<sha256>.md),
-- so a statute collected for many jurisdictions is one object and many rows.

BEGIN;

ALTER TABLE jurisdictions ADD COLUMN IF NOT EXISTS extras_governing_law jsonb;

CREATE TABLE IF NOT EXISTS governing_law_source_pages (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction_ocdid text NOT NULL REFERENCES jurisdictions(jurisdiction_ocdid),
    source_url         text NOT NULL CHECK (source_url <> ''),
    page_hash          text NOT NULL,
    cache_path         text NOT NULL,
    collected_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS governing_law_source_pages_jurisdiction_ocdid_idx
    ON governing_law_source_pages (jurisdiction_ocdid);

COMMIT;
