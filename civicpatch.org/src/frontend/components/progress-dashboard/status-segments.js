export const STATUS_ORDER = ["fresh", "stale", "gap", "untracked"];

export const STATUS_LABELS = {
  fresh: "Fresh",
  stale: "Stale",
  gap: "Not yet scraped",
  untracked: "Untracked",
};

export function computeStatusSegments(statusCounts = {}) {
  const total = STATUS_ORDER.reduce(
    (sum, key) => sum + (statusCounts[key] ?? 0),
    0,
  );
  return STATUS_ORDER.map((key) => {
    const count = statusCounts[key] ?? 0;
    return {
      key,
      count,
      percent: total > 0 ? (count / total) * 100 : 0,
    };
  });
}
