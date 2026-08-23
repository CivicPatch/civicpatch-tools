BEGIN;

-- Why a request left the review pool, where `dismissed_at` only records that it did.
--
-- Two automated dismissals are about to mean opposite things. `supersede_stacked_requests`
-- discards a scrape nobody read, in favour of a newer one — we learned nothing from it.
-- Auto-resolve retires a scrape whose roster matched what we already hold — we learned the
-- source still says this, and `memberships.last_seen_at` moved to prove it. Both set
-- `dismissed_at`, so without this they are the same row.
--
-- That matters at scale rather than now: weekly scrapes across ~3,800 jurisdictions are mostly
-- no-change, so most of this table will end up dismissed. A history where "dismissed" means
-- both "confirmed current" and "thrown away unread" cannot answer either question.
--
-- A reason, not a third status. `RequestReviewStatus` derives from `published_at`/`dismissed_at`
-- and a CHECK forbids both — the lifecycle position really is the same for both cases, so the
-- enum should not grow. NULL is every row written before this and every human dismissal.
ALTER TABLE requests ADD COLUMN dismissed_reason text;

COMMENT ON COLUMN requests.dismissed_reason IS
    'Why the request left the pool: superseded (discarded unread) | unchanged (roster confirmed). NULL = human or pre-dating this column.';

COMMIT;
