-- `no_info` becomes `no_roster_found`.
--
-- Its two neighbours in `PipelineRunErrorType` name a fault in the source — `domain_inactive`,
-- `domain_navigation_error` — and `no_info` sat beside them reading like a third. It is the
-- opposite: the domain resolved, navigation worked, the pages read fine, and there was simply
-- no roster published where we could find it. Searching for a better source is part of that
-- outcome, not a failure preceding it.
--
-- The distinction matters because this row is going on a jurisdiction's timeline: "found no
-- roster" is an outcome a maintainer can act on by supplying a URL. "no_info" reads as a crash.
--
-- `issue_type` has no CHECK constraint, so nothing to alter — this is a data rename. Idempotent
-- because a second run matches no rows.

BEGIN;

UPDATE issues SET issue_type = 'no_roster_found' WHERE issue_type = 'no_info';

COMMIT;
