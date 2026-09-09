interface StatusCounts {
  fresh: number;
  stale: number;
}

export interface DashboardState {
  civicpatch: {
    localities: { known: number };
    status_counts: StatusCounts;
    needs_review: number;
  };
}

export function sortedRows(statesData: Record<string, DashboardState>) {
  return Object.entries(statesData)
    .map(([code, data]) => {
      const { known } = data.civicpatch.localities;
      const { fresh, stale } = data.civicpatch.status_counts;
      return { code, known, fresh, stale, needsReview: data.civicpatch.needs_review };
    })
    .filter((row) => row.known > 0)
    .sort((a, b) => b.needsReview - a.needsReview);
}
