BEGIN;

-- `assertions` stops being a log and becomes current state.
--
-- Plan: .scratch/2026-08-24-assertions-accept-reject.md. Empty table, so this is a clean swap.
--
-- `accept`  — this value stands. Written at publish, for each non-null value the reviewer saw.
-- `reject`  — never this value. Written when a reviewer removes one.
--
-- Neither is a button, which is what retires `confirm`: a valueless third kind that existed so
-- somebody could say "I looked". Publishing says it.
--
-- `correct` goes for a second reason. It is the only value here that reads as an adjective, and
-- the adjective means "accurate" — a near-synonym of the `confirm` sitting beside it. The old
-- constraint name says it out loud: `assertions_correct_has_value` parses as "a correct value
-- has a value".
ALTER TABLE assertions DROP CONSTRAINT assertions_kind_check;
ALTER TABLE assertions ADD CONSTRAINT assertions_kind_check
    CHECK (kind = ANY (ARRAY['accept'::text, 'reject'::text]));

-- Both kinds carry a value about a field, so both columns are required — and that is what
-- dissolves the question this design kept running aground on: what `value = NULL` meant.
-- Clearing a phone is a *reject of that number*, not a null accept. A field the reviewer saw
-- empty gets no row at all, and the scraper keeps owning it.
ALTER TABLE assertions ALTER COLUMN field_path SET NOT NULL;
ALTER TABLE assertions ALTER COLUMN value SET NOT NULL;

-- Superseded by the NOT NULL above: it existed to force a value onto a `correct`.
ALTER TABLE assertions DROP CONSTRAINT assertions_correct_has_value;

-- Keyed on `asserted_at`, so it only ever prevented two rows written in the same instant. That
-- made sense while rows accumulated and the latest won. They do not accumulate now.
ALTER TABLE assertions DROP CONSTRAINT assertions_no_exact_duplicate;

-- The rules, as constraints rather than as conventions every reader has to remember.
--
-- They get forgotten: `POST_IS_VERIFIED` matches any `confirm` ever and ignores a later
-- `retract`, so an un-vouched post stays verified forever. Latest-wins was stated in a
-- docstring and implemented in exactly one reader.
--
-- Scalar fields have one answer, so one accept.
CREATE UNIQUE INDEX assertions_one_accept_per_scalar_field
    ON assertions (entity_type, entity_id, field_path)
    WHERE kind = 'accept'
      AND field_path NOT IN ('other_names', 'phones', 'emails', 'urls', 'source_urls');

-- List fields are sets: `(scraped ∪ accepted) − rejected`, both kinds naming one element. Same
-- rule covers rejects everywhere, which are per-value by definition.
CREATE UNIQUE INDEX assertions_one_row_per_value
    ON assertions (entity_type, entity_id, field_path, value)
    WHERE kind = 'reject'
       OR field_path IN ('other_names', 'phones', 'emails', 'urls', 'source_urls');

COMMIT;
