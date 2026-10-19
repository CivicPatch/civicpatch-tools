-- What a jurisdiction's governing law says its government is made of, in Open Civic Data's
-- Organization and Post shape (shared.schemas.GoverningLawOrganizations). cp.org's own, written
-- only by the organizations collector; NULL until its run reads this jurisdiction's law.

BEGIN;

ALTER TABLE jurisdictions ADD COLUMN IF NOT EXISTS extras_organizations jsonb;

COMMIT;
