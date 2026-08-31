-- Three tables nothing reads, and the dead two thirds of a fourth.
--
-- `sync_log` — created by 003 and never touched again. It recorded a sync's commit and file
-- count; `synced_files` replaced that with a per-path cursor, and no code has referenced this
-- table since. 0 rows.
--
-- `logs` — created by 001_init, 0 rows, no reader. Application logs go to Grafana. Its only
-- structural tie is an FK to `api_keys`, which stays.
--
-- `state_configs` — `state TEXT PRIMARY KEY` and nothing else. 103 dropped `min_scraped_at`
-- when freshness became a computed rolling window and kept the shell "as the home for the next
-- per-state setting". Two months on it holds none, has no reader, and `jurisdictions.state`
-- already answers which states exist. **This reverses a documented intent** (DATABASE.md said
-- deliberately kept) — bringing it back is one statement if a setting ever arrives, which is
-- less than the cost of a table that reads as meaningful and is not.
--
-- `synced_files` — keep the table, delete the rows for a direction that no longer exists.
-- 45 `data_source/**` rows are the live cursor `sync_all` tree-diffs against. 3,430 `data/**`
-- rows are cursors for people files, and `sync_all` discards the people half of the diff
-- (`current_jurisdictions, _ = get_current_tree(tree)`). Worse than merely unread: `data/**` is
-- now rendered *from* the database and overwritten on every publish, so each stored SHA gets
-- staler with every write. The code that computes them goes with this migration.
BEGIN;

DROP TABLE IF EXISTS sync_log;

DROP TABLE IF EXISTS logs;

DROP TABLE IF EXISTS state_configs;

DELETE FROM synced_files WHERE path LIKE 'data/%';

COMMIT;
