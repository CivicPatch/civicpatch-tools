-- What we last wrote to each outward destination, so a sweep can tell "this changed" from
-- "I already wrote this".
--
-- The sweep selects on `change_logs` in a 15-minute lookback and runs every 5 minutes, so the
-- same change is selected three times. Nothing recorded that the work was done, so all three
-- wrote. Measured on one email edit to Seattle on 2026-09-04:
--
--   15:30  commit 37501393   the real one
--   15:35  commit c70e7ef4   empty — identical file
--   15:40  commit 812ffffe   empty — identical file, and it took over `change_url`
--
-- Plus three full rewrites of Live[People][WA], Live[Memberships][WA] and Live[Posts][WA],
-- about 9,700 rows re-uploaded for one changed cell. The amplification is ceil(lookback /
-- cadence) on every write, to every sink.
--
-- `target` is the destination itself rather than a (sink, key) pair, because each sink already
-- names what it writes: `reviewed_file_path(ocdid)` gives "data/us/wa/seattle.yml",
-- `people_tab(state)` gives "Live[People][WA]". The namespaces cannot collide, so a `sink`
-- column would discriminate nothing.
--
-- `content_hash` is of the rendered *rows*, not of the bytes the sink sends. Parquet encoding is
-- not byte-stable — compression, metadata timestamps and row-group boundaries vary run to run —
-- so hashing the encoded file would never match and the gate would be silently dead. Git is the
-- case where the two coincide, because the YAML string is the artifact.
--
-- This is `synced_files` pointed outward. That table holds the git blob SHA last read per path,
-- which is why the hourly sync makes one API call instead of re-fetching every file. Same gate,
-- opposite direction:
--
--   synced_files   (path,   blob_sha,     synced_at)   what we last READ from open-data
--   output_hashes  (target, content_hash, written_at)  what we last WROTE anywhere

BEGIN;

CREATE TABLE IF NOT EXISTS output_hashes (
    target        text PRIMARY KEY,
    content_hash  text NOT NULL,
    written_at    timestamptz NOT NULL DEFAULT now()
);

COMMIT;
