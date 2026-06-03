BEGIN;

-- Give the global canonical roles a sensible default ordering so the taxonomy
-- editor (and the pipeline, which ranks roles by their position in the
-- priority-sorted list) leads with mayor instead of falling back to the
-- alphabetical tiebreak. Order mirrors the curated hierarchy in
-- 097_seed_role_taxonomy.up.sql. Only global (jurisdiction_ocdid IS NULL)
-- canonical terms are seeded; state/locality terms keep priority 0 until
-- explicitly reordered.

UPDATE role_terms AS t
SET priority = v.priority
FROM (VALUES
    ('mayor', 0),
    ('mayor pro tempore', 1),
    ('assistant mayor', 2),
    ('deputy mayor', 3),
    ('vice mayor', 4),
    ('commission president', 5),
    ('commissioner vice president', 6),
    ('commissioner', 7),
    ('deputy mayor pro tempore', 8),
    ('council president', 9),
    ('council president pro tem', 10),
    ('deputy council president', 11),
    ('council vice president', 12),
    ('council manager', 13),
    ('council member', 14),
    ('committee member', 15),
    ('select board chair', 16),
    ('select board vice chair', 17),
    ('select board member', 18),
    ('president board of aldermen', 19),
    ('vice president board of aldermen', 20),
    ('alderperson', 21),
    ('chair', 22),
    ('vice chair', 23),
    ('chair pro tem', 24),
    ('president pro tempore', 25)
) AS v(value, priority)
WHERE t.value = v.value
  AND t.jurisdiction_ocdid IS NULL
  AND t.kind = 'canonical';

-- Reordering the taxonomy emits one aggregate change_log per scope save.
INSERT INTO change_log_types (type) VALUES ('reorder_roles');

COMMIT;
