-- The five titles that account for 89% of unresolvable labels, plus their deputies.
--
-- Measured over open-data 2026-08-18: 4,824 of 22,987 published people (21.0%) resolve to no
-- role. Five titles cover 4,312 of them — Trustee 1,943 · Alderperson 787 · Clerk 592 ·
-- Supervisor 520 · Treasurer 470. All published, none in the taxonomy. This is the same list
-- the flat-roles plan measured independently in August, grown but unchanged in shape.
--
-- Deputies are only added where the corpus has them: Deputy Clerk 8, Deputy Treasurer 8,
-- Deputy Supervisor 4. There is no deputy trustee or deputy alderperson in the data, so
-- none is invented here.
--
-- NOT added: 'City Secretary' -> secretary, and 'City Manager' -> council-manager. Production
-- carries roles `city-secretary` and `city-manager` whose *labels* are exactly those strings.
-- An alias may not claim a label another role already claims — `upsert_roles` refuses to save
-- such a taxonomy, and that is the admin UI's save path, so adding them would have made every
-- role edit return 409. The unique index would not have caught it: it covers alias labels, not
-- role labels, so `ON CONFLICT DO NOTHING` sails straight past.
--
-- Dev has neither role, which is why this was invisible here and only surfaced against the
-- integration database. Verified against production 2026-08-20, before 119 had shipped.
--
-- 'Town Manager' is left in. Production has it as an alias of `city-manager`, so the alias
-- unique index does catch that one and `ON CONFLICT DO NOTHING` skips it.
--
-- `Alderperson` does not collide: `council-member`'s 33 aliases include councilman,
-- councilor and councilperson but no alderman, and the taxonomy already carries
-- `president-board-of-aldermen` with no plain member beneath it.
--
-- Priorities follow dev's existing bands — members at 500+, officers after them, each deputy
-- just below its base so the base wins when both appear across labels. These are absolute
-- numbers against a taxonomy that is edited through the admin UI, so an environment whose
-- bands have drifted will get the right roles in a slightly wrong usurp order. That is
-- recoverable with an UPDATE; a failed migration is not, which is why every statement here
-- skips rather than errors.
--
-- `is_unique` false for Supervisor deliberately: a township supervisor is one person and a
-- county supervisor is one of several, and marking it unique would flag every county board.
-- False lets `posts.headcount` take the observed count, which is right in both cases.
BEGIN;

INSERT INTO roles (id, label, status, is_unique, priority) VALUES
    ('alderperson',       'Alderperson',       'active', false, 505),
    ('trustee',           'Trustee',           'active', false, 540),
    ('supervisor',        'Supervisor',        'active', false, 550),
    ('deputy-supervisor', 'Deputy Supervisor', 'active', true,  560),
    ('clerk',             'Clerk',             'active', true,  610),
    ('deputy-clerk',      'Deputy Clerk',      'active', true,  620),
    ('treasurer',         'Treasurer',         'active', true,  630),
    ('deputy-treasurer',  'Deputy Treasurer',  'active', true,  640),
    -- The second pass, after the five above dropped unmatched from 21.0% to 0.4%.
    -- Assessor is not unique: a board of assessors is three people.
    ('moderator',         'Moderator',         'active', true,  650),
    ('secretary',         'Secretary',         'active', true,  660),
    ('assessor',          'Assessor',          'active', false, 670)
ON CONFLICT DO NOTHING;

-- Re-activate on re-apply. The insert above cannot do this: `ON CONFLICT DO NOTHING` is a
-- no-op for a row that exists, so after the down sets these `inactive` the up could never
-- bring them back. It has to be untargeted there — targeting `id` would crash on a prod role
-- that already holds one of these labels under a different id — hence a second statement.
-- Scoped to the ids this migration owns, so nothing else is touched.
UPDATE roles SET status = 'active' WHERE id IN (
    'alderperson', 'trustee', 'supervisor', 'deputy-supervisor',
    'clerk', 'deputy-clerk', 'treasurer', 'deputy-treasurer',
    'moderator', 'secretary', 'assessor'
) AND status = 'inactive';

-- Maintainer-entered aliases land `active`: typing one is approval.
INSERT INTO role_aliases (role_id, label, status)
SELECT v.role_id, v.label, 'active'
FROM (VALUES
    ('alderperson', 'Alderman'),
    ('alderperson', 'Alderwoman'),
    ('alderperson', 'Aldermen'),
    ('trustee', 'Trustees'),
    ('trustee', 'Township Trustee'),
    ('trustee', 'Village Trustee'),
    ('supervisor', 'Township Supervisor'),
    ('supervisor', 'Town Supervisor'),
    ('clerk', 'City Clerk'),
    ('clerk', 'Town Clerk'),
    ('clerk', 'Township Clerk'),
    ('clerk', 'Village Clerk'),
    ('clerk', 'Borough Clerk'),
    ('clerk', 'Municipal Clerk'),
    ('treasurer', 'City Treasurer'),
    ('treasurer', 'Town Treasurer'),
    ('treasurer', 'Township Treasurer'),
    ('treasurer', 'Village Treasurer'),
    ('deputy-clerk', 'Deputy City Clerk'),
    ('deputy-clerk', 'Deputy Town Clerk'),
    ('deputy-clerk', 'Deputy Township Clerk'),
    ('deputy-treasurer', 'Deputy City Treasurer'),
    ('deputy-treasurer', 'Deputy Township Treasurer'),
    ('moderator', 'Town Moderator'),
    ('secretary', 'Town Secretary'),
    ('assessor', 'Township Assessor'),
    ('assessor', 'City Assessor'),
    -- `council-manager` had no aliases at all, so the appointed manager never matched.
    ('council-manager', 'Town Manager'),
    ('council-manager', 'Township Manager'),
    ('council-manager', 'Village Manager'),
    -- Spelling variants of roles that already exist.
    ('committee-member', 'Committeeperson'),
    ('committee-member', 'Committeewomen'),
    ('committee-member', 'Committee Woman'),
    ('chair', 'Chairperson'),
    ('vice-chair', 'Vice Chairperson'),
    ('vice-chair', 'Vice-Chairperson'),
    ('select-board-member', 'Select Person'),
    -- Not a missing role: select-board-member already has selectman/selectmen/selectwoman.
    ('select-board-member', 'Selectperson')
) AS v(role_id, label)
-- Skip rather than fail when the parent role is absent: prod's taxonomy is edited
-- through the admin UI, so it is not guaranteed to match dev's.
WHERE EXISTS (SELECT 1 FROM roles r WHERE r.id = v.role_id)
ON CONFLICT DO NOTHING;

-- DELIBERATELY NOT ADDED, and left to fall through to Unmatched:
--   Pro-Tem · Pro Tem · Protem · Pro Tempore · Pro-Tempore · Village Pro Tem  (17 people)
--     Fragments, not offices. A record whose entire title is "Pro-Tem" does not say what the
--     person is; `mayor-pro-tempore` and friends already exist for the full forms.
--   Committee (3) · Place 1 (1)
--     A body and a designation, neither of them a role.
--   Office Manager · Accountant · Administrative Assistant · Superintendent · City Recorder ·
--   Town Administrator · General Assistance Administrator  (1 each)
--     Municipal staff rather than offices, and one observation apiece is not enough to say
--     which. They belong in triage, not in the taxonomy on this evidence.

COMMIT;
