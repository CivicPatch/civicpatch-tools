/**
 * How many reviews are ready right now: the lesser of what's available and how
 * many remain before the daily goal, never below zero.
 *
 * `availableCount` already excludes PRs resolved today — publishing merges a PR
 * out of the `open` pool, so the count shrinks by one per review on its own.
 * We therefore clamp by `dailyGoal - todayResolved` and do NOT also subtract
 * `todayResolved` from `availableCount`; doing both double-counts and makes the
 * number bottom out at 0 while PRs are still available.
 *
 * Used for both the landing "Ready for Review" count and the in-session dot
 * total, so the two can never disagree.
 */
export function reviewsReady(
  availableCount: number,
  dailyGoal: number,
  todayResolved: number,
): number {
  return Math.max(0, Math.min(availableCount, dailyGoal - todayResolved));
}
