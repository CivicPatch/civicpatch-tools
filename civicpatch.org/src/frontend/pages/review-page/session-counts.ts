export const SESSION_COUNTS = [5, 10, 25, 50];

export function sessionCountsFor(available: number): number[] {
  if (available > 0 && available < SESSION_COUNTS[0]) return [available];
  return SESSION_COUNTS;
}
