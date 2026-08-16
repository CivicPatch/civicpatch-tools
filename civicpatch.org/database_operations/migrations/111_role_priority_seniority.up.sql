-- Re-order roles.priority to encode seniority, not display specificity.
--
-- priority is read by sort_roles/sort_people for display, and is about to become the signal
-- that decides which role usurps the others when a person holds more than one (21% of
-- published people do: 4,274 of 20,711). The existing order cannot carry that meaning:
--
--     3  Deputy Mayor Pro Tempore
--     4  Mayor                      <- Mayor below Deputy Mayor Pro Tempore
--    14  Council Member
--    20  Mayor Pro Tempore          <- and below Council Member
--    23  Vice Chair
--    24  Chair                      <- backwards under any reading
--
-- Lowest-wins on that would turn a Mayor who is also Deputy Mayor Pro Tem into "Deputy Mayor
-- Pro Tempore", and the commonest real pair (Council Member + Mayor Pro-Tem) into plain
-- "Council Member".
--
-- is_unique was considered as the signal instead and rejected: Chair, Vice Chair and Select
-- Board Chair are all is_unique = false (many committees each have a chair), so it gives no
-- usurp at all for Select Board Chair + Select Board Member.
--
-- The ordering below groups presiding and singular offices above body-membership roles. That
-- boundary is the only part load-bearing for the usurp rule; order *within* a group affects
-- display only, and is left approximate deliberately — whether Vice Mayor outranks Mayor Pro
-- Tempore varies by state, and the roles admin UI (config-editor.js) exists to curate it.
--
-- The 200 block is the exception: it is ordered by *tier*, not by body. Grouping it by body
-- put a vice chair above a chair (Select Board Vice Chair 210 over Chair 220) and a board
-- president below a generic vice chair (President, Board of Aldermen 250 over Vice Chair 230).
-- Under lowest-wins those invert real seniority, so the block runs presiding, then
-- vice-presiding, then pro-tem. Within a tier, a title naming its body outranks the bare
-- generic — "President, Board of Aldermen" is a more specific claim than an unqualified
-- "Chair".
--
-- Numbers are spaced by 10s so a role can be inserted between two others without renumbering
-- the table. 500 is the usurp line: below it, presiding and singular offices; at or above it,
-- body membership.
BEGIN;

UPDATE roles AS r
SET priority = v.priority
FROM (
    VALUES
        -- mayoral
        ('mayor', 10),
        ('deputy-mayor', 20),
        ('vice-mayor', 30),
        ('assistant-mayor', 40),
        ('mayor-pro-tempore', 50),
        ('deputy-mayor-pro-tempore', 60),
        -- council presiding
        ('council-president', 100),
        ('council-vice-president', 110),
        ('council-president-pro-tem', 120),
        ('deputy-council-president', 130),
        ('president-pro-tempore', 140),
        -- board presiding
        ('select-board-chair', 200),
        ('president-board-of-aldermen', 210),
        ('chair', 220),
        -- board vice-presiding
        ('select-board-vice-chair', 230),
        ('vice-president-board-of-aldermen', 240),
        ('commissioner-vice-president', 250),
        ('vice-chair', 260),
        -- pro-tem
        ('chair-pro-tem', 270),
        -- ---- usurp line: everything below is body membership ----
        ('council-member', 500),
        ('select-board-member', 510),
        ('commissioner', 520),
        ('committee-member', 530),
        -- appointed
        ('council-manager', 600)
) AS v (id, priority)
WHERE r.id = v.id;

COMMIT;
