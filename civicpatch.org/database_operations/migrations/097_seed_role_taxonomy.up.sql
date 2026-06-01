BEGIN;

-- Seed the global (jurisdiction_ocdid IS NULL) role taxonomy from the
-- open-data config snapshot (see seed/role_taxonomy.yml). Idempotent:
-- ON CONFLICT DO NOTHING bootstraps an empty environment (prod) and is a
-- no-op where the taxonomy already exists (dev). The DB stays the source
-- of truth; this only fills an empty global scope, never overwrites.

INSERT INTO role_terms (value, kind, jurisdiction_ocdid, display_name, is_unique, priority) VALUES
    ('mayor', 'canonical', NULL, 'mayor', TRUE, 0),
    ('mayor pro tempore', 'canonical', NULL, 'mayor pro tempore', TRUE, 0),
    ('assistant mayor', 'canonical', NULL, 'assistant mayor', TRUE, 0),
    ('deputy mayor', 'canonical', NULL, 'deputy mayor', TRUE, 0),
    ('vice mayor', 'canonical', NULL, 'vice mayor', TRUE, 0),
    ('commission president', 'canonical', NULL, 'commission president', TRUE, 0),
    ('commissioner vice president', 'canonical', NULL, 'commissioner vice president', TRUE, 0),
    ('commissioner', 'canonical', NULL, 'commissioner', FALSE, 0),
    ('deputy mayor pro tempore', 'canonical', NULL, 'deputy mayor pro tempore', TRUE, 0),
    ('council president', 'canonical', NULL, 'council president', TRUE, 0),
    ('council president pro tem', 'canonical', NULL, 'council president pro tem', TRUE, 0),
    ('deputy council president', 'canonical', NULL, 'deputy council president', TRUE, 0),
    ('council vice president', 'canonical', NULL, 'council vice president', TRUE, 0),
    ('council manager', 'canonical', NULL, 'council manager', TRUE, 0),
    ('council member', 'canonical', NULL, 'council member', FALSE, 0),
    ('committee member', 'canonical', NULL, 'committee member', FALSE, 0),
    ('select board chair', 'canonical', NULL, 'select board chair', FALSE, 0),
    ('select board vice chair', 'canonical', NULL, 'select board vice chair', TRUE, 0),
    ('select board member', 'canonical', NULL, 'select board member', FALSE, 0),
    ('president board of aldermen', 'canonical', NULL, 'president board of aldermen', TRUE, 0),
    ('vice president board of aldermen', 'canonical', NULL, 'vice president board of aldermen', TRUE, 0),
    ('alderperson', 'canonical', NULL, 'alderperson', FALSE, 0),
    ('chair', 'canonical', NULL, 'chair', FALSE, 0),
    ('vice chair', 'canonical', NULL, 'vice chair', FALSE, 0),
    ('chair pro tem', 'canonical', NULL, 'chair pro tem', TRUE, 0),
    ('president pro tempore', 'canonical', NULL, 'president pro tempore', TRUE, 0),
    ('city manager', 'exclusion', NULL, 'city manager', TRUE, 0),
    ('city attorney', 'exclusion', NULL, 'city attorney', TRUE, 0),
    ('city secretary', 'exclusion', NULL, 'city secretary', TRUE, 0)
ON CONFLICT ON CONSTRAINT role_terms_scope_uq DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('mayor protem'), ('mayor protemp'), ('mayor pro-tem'), ('mayor pro-temp'), ('mayor pro tem'), ('mayor pro temp'), ('mayor pro-tempore'), ('mayor-pro tem')) AS a(value)
WHERE t.value = 'mayor pro tempore' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('vice-mayor')) AS a(value)
WHERE t.value = 'vice mayor' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('commissioner president')) AS a(value)
WHERE t.value = 'commission president' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('commissioner vice-president'), ('commissioner-vice president'), ('commission vice-president'), ('commission vice president')) AS a(value)
WHERE t.value = 'commissioner vice president' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('city commissioner')) AS a(value)
WHERE t.value = 'commissioner' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('deputy mayor pro tem'), ('deputy mayor pro-tem'), ('deputy mayor pro tempore')) AS a(value)
WHERE t.value = 'deputy mayor pro tempore' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('president'), ('city council president'), ('council member president'), ('president of the council')) AS a(value)
WHERE t.value = 'council president' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('council president pro-tem'), ('council president pro tempore')) AS a(value)
WHERE t.value = 'council president pro tem' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('vice president'), ('vice-president'), ('council vice-president'), ('council member vice president'), ('council member vice-president')) AS a(value)
WHERE t.value = 'council vice president' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('council-member'), ('city councilor'), ('town councilor'), ('council member at-large'), ('councilperson'), ('council person'), ('councilmember'), ('councilmembers'), ('councilwoman'), ('councilman'), ('councilor'), ('councillor'), ('city councilman'), ('city councilwoman'), ('city councilmember'), ('city council member'), ('city council'), ('town council representative'), ('town council member'), ('town councilmember'), ('town council'), ('town board member'), ('representative'), ('council'), ('member'), ('councilmen'), ('councilwomen'), ('council members'), ('councilperson at-large'), ('councilwoman at large'), ('councilman-at-large'), ('councilwoman-at-large'), ('council at large')) AS a(value)
WHERE t.value = 'council member' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('township committee member'), ('committeeman'), ('committeewoman'), ('committee person')) AS a(value)
WHERE t.value = 'committee member' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('selectboard chairman'), ('selectboard chairwoman'), ('select board chairman'), ('select board chairwoman'), ('selectboard chair')) AS a(value)
WHERE t.value = 'select board chair' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('select board vice chairman'), ('select board vice chairwoman'), ('select board vice-chair'), ('select board vice-chairman'), ('select board vice-chairwoman'), ('selectboard vice chair'), ('selectboard vice chairman'), ('selectboard vice chairwoman'), ('selectboard vice-chair'), ('selectboard vice-chairman'), ('selectboard vice-chairwoman')) AS a(value)
WHERE t.value = 'select board vice chair' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('selectmen'), ('selectman'), ('selectwoman'), ('select board'), ('board of selectmen'), ('board of selectmen member'), ('select board representative'), ('selectboard'), ('selectboard member'), ('select board member')) AS a(value)
WHERE t.value = 'select board member' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('alder'), ('alderman'), ('aldermen'), ('alderwoman'), ('city alderman'), ('city alderwoman'), ('city council alderman'), ('city council alderwoman')) AS a(value)
WHERE t.value = 'alderperson' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('council chair'), ('council chairman'), ('council chairwoman'), ('chairman'), ('chairwoman'), ('town council chair')) AS a(value)
WHERE t.value = 'chair' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('council vice chair'), ('council vice chairman'), ('council vice chairwoman'), ('council vice-chair'), ('council vice-chairman'), ('council vice-chairwoman'), ('vice-chair'), ('vice-chairman'), ('vice-chairwoman'), ('vice chairman'), ('vice chairwoman')) AS a(value)
WHERE t.value = 'vice chair' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('president pro tem')) AS a(value)
WHERE t.value = 'president pro tempore' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('city administrator'), ('town manager'), ('village manager')) AS a(value)
WHERE t.value = 'city manager' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

INSERT INTO role_aliases (term_id, value, source)
SELECT t.id, a.value, 'curated'
FROM role_terms t
CROSS JOIN (VALUES ('municipal attorney'), ('town attorney'), ('village attorney'), ('city solicitor')) AS a(value)
WHERE t.value = 'city attorney' AND t.jurisdiction_ocdid IS NULL
ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING;

COMMIT;
