BEGIN;

-- The system is an actor, so it gets a row rather than a null.
--
-- Three columns carried "nobody" as NULL: `change_logs.user_id`,
-- `changesets.created_by_user_id` and `changesets.resolved_by_user_id`. That made a supersede
-- sweep or an auto-publish indistinguishable from an unattributed write, and every reader had
-- to know the convention. `assertions.asserted_by` already refuses nulls for the same reason —
-- an assertion nobody made is not an assertion.
--
-- Nothing can log in as this row. `upsert_user` is the only writer of `users` on the auth path,
-- its single caller passes `SupabaseUser.provider`, and that is a hardcoded property returning
-- 'supabase' — so a row with provider 'system' can never be matched or overwritten by a login.
-- The email uses `.invalid`, RFC 2606's reserved TLD, so it can never route anywhere.
-- Role is `default`: least privilege, and the system never passes through `require_route_access`.
INSERT INTO users (id, provider, provider_user_id, email, display_name, role)
VALUES (
    '00000000-0000-4000-8000-000000000001',
    'system',
    'civicpatch',
    'system@civicpatch.invalid',
    'CivicPatch',
    'default'
)
ON CONFLICT (id) DO NOTHING;

UPDATE change_logs
SET user_id = '00000000-0000-4000-8000-000000000001'
WHERE user_id IS NULL;

UPDATE changesets
SET created_by_user_id = '00000000-0000-4000-8000-000000000001'
WHERE created_by_user_id IS NULL;

-- Resolved rows only. A pending changeset genuinely has no resolver, and that null is the whole
-- point of the change: afterwards `resolved_by_user_id IS NULL` means "not resolved yet" and
-- nothing else.
UPDATE changesets
SET resolved_by_user_id = '00000000-0000-4000-8000-000000000001'
WHERE resolved_by_user_id IS NULL
  AND (published_at IS NOT NULL OR dismissed_at IS NOT NULL);

-- The columns stay nullable on purpose. Attributing system actions and forbidding nulls are
-- two changes: writers still exist that pass none, and a `SET NOT NULL` here fails 52 of them
-- at once. They are being converted to write the system user, and once no nulls are produced
-- the constraint can land on its own, with the tests to prove it.

COMMIT;
