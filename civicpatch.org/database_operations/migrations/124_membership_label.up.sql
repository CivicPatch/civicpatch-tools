-- What this person's seat is *called*, when a person has said so.
--
-- 122 split `memberships.label` into `designations` and `unmatched_text` and dropped it,
-- treating the label as purely derived. It is not. We can only reconstruct one — role plus
-- designations plus division plus unmatched text — and the reconstruction is a guess that will
-- not match what the page said. "Council Member, Position 8" against "Councilmember Pos. 8".
--
-- So the label comes back, human-owned, beside the derived parts rather than instead of them:
--
--   designations     derived, rewritten every publish
--   unmatched_text   derived, rewritten every publish
--   label            a person's, never written by the derivation
--
-- Reads are COALESCE(label, <assembled from the parts>) — the same "human wins, derivation
-- fills in" shape as `posts.label` and `posts.headcount`.
--
-- What protects it is `memberships.record` leaving it out of the ON CONFLICT DO UPDATE set. A
-- post cannot change its own role or division (PATCH reaches only label and headcount, and the
-- identity triple is the primary key), so the only thing that disturbs a set label is the
-- person landing on a *different* post — which closes this membership and opens a new one with
-- no label. That is correct: a different seat is a different thing to name.

BEGIN;

ALTER TABLE memberships
    ADD COLUMN IF NOT EXISTS label text;

COMMIT;
