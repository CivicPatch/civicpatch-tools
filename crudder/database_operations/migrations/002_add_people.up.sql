BEGIN;

CREATE TABLE IF NOT EXISTS "people" (
    "jurisdiction_ocdid" text NOT NULL,
    "name" text NOT NULL,
    "data" jsonb NOT NULL,
    PRIMARY KEY ("jurisdiction_ocdid", "name")
);

COMMIT;
