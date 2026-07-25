# The one definition of "recently scraped", shared by the coverage, dashboard, and
# candidate-queue queries. Fresh is simply the complement of stale: one boundary, and a
# scrape is on one side of it or the other. Evaluated per query rather than stored, so it
# rolls forward on its own — a jurisdiction ages out 90 days after its last scrape and
# re-enters the scrape queue with no admin action. Trades the old per-state cutoff's
# monotonic progress (a state that hit 100% stayed there) for a self-maintaining
# re-scrape schedule.
#
# Days, not `interval '3 months'`: calendar months vary from 89 to 92 days, which would
# make the boundary drift with the season for no benefit.
FRESH_SINCE_SQL = "now() - interval '90 days'"
