BEGIN;

-- Reverse the global taxonomy seed. Deletes the seeded global-scope terms
-- by value; role_aliases rows cascade (term_id ON DELETE CASCADE).
-- Caveat: also removes any aliases/edits attached to these global terms
-- after seeding — rolling back 097 unwinds the seed and its descendants.

DELETE FROM role_terms
WHERE jurisdiction_ocdid IS NULL
  AND value IN (
    'mayor',
    'mayor pro tempore',
    'assistant mayor',
    'deputy mayor',
    'vice mayor',
    'commission president',
    'commissioner vice president',
    'commissioner',
    'deputy mayor pro tempore',
    'council president',
    'council president pro tem',
    'deputy council president',
    'council vice president',
    'council manager',
    'council member',
    'committee member',
    'select board chair',
    'select board vice chair',
    'select board member',
    'president board of aldermen',
    'vice president board of aldermen',
    'alderperson',
    'chair',
    'vice chair',
    'chair pro tem',
    'president pro tempore',
    'city manager',
    'city attorney',
    'city secretary'
  );

COMMIT;
