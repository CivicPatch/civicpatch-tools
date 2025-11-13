s BEGIN;

CREATE TABLE IF NOT EXISTS geo (
    geoid TEXT PRIMARY KEY,
    geom geometry,
    meta JSONB,
    statefp TEXT,
    name TEXT,
    funcstat TEXT,
    type TEXT,
    file_path TEXT,
    git_commit TEXT,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX geo_geom_gix ON geo USING GIST (geom);
CREATE INDEX jurisdictions_meta_geoid_idx ON jurisdictions ((data->>'geoid'));

COMMIT;
