BEGIN;

-- `core.membership_label.render` used to fold the post's own name into `memberships.label`
-- seat-first — "Council Member, District 5, Chair" — so every row written before that reversed
-- still has the seat's name baked in, which now reads as the post label and the membership
-- label simply repeating each other. Clearing it lets a scrape re-derive a clean value.
UPDATE memberships SET label = NULL WHERE label IS NOT NULL;

-- Withdraw every accept assertion on a membership's label. `LABEL_IS_HUMAN_SET`
-- (database/memberships.py) would otherwise keep a future scrape from ever writing a fresh
-- value back, no matter what the column above now says. A human's genuine correction is
-- indistinguishable at this layer from the stale text the label input itself used to
-- pre-fill (before the picker was fixed to stop showing it) — so this withdraws all of it
-- rather than guessing which rows were which; anyone who still wants their own wording types
-- it again.
UPDATE assertions
   SET withdrawn_at = now(),
       withdrawn_by = '00000000-0000-4000-8000-000000000001',
       withdrawn_reason = 'stale composed label cleared (post label no longer folded in)'
 WHERE entity_type = 'membership'
   AND field_path = 'label'
   AND kind = 'accept'
   AND withdrawn_at IS NULL;

COMMIT;
