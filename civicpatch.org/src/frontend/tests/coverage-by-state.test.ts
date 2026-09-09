import { describe, it, expect } from "vitest";
import { sortedRows } from "../pages/home-page/coverage-by-state-model.js";

const state = (known: number, fresh: number, stale: number, needsReview: number) => ({
  civicpatch: {
    localities: { known },
    status_counts: { fresh, stale },
    needs_review: needsReview,
  },
});

describe("sortedRows", () => {
  it("carries the coverage bar counts and the needs-review count", () => {
    const rows = sortedRows({ wa: state(10, 3, 2, 5) });
    expect(rows).toEqual([{ code: "wa", known: 10, fresh: 3, stale: 2, needsReview: 5 }]);
  });

  it("drops states with no known municipalities", () => {
    const rows = sortedRows({ wa: state(10, 3, 0, 1), ak: state(0, 0, 0, 0) });
    expect(rows.map((r) => r.code)).toEqual(["wa"]);
  });

  it("keeps states with nothing awaiting review — every state is listed", () => {
    const rows = sortedRows({ wa: state(10, 5, 0, 0), ak: state(10, 3, 0, 2) });
    expect(rows.map((r) => r.code)).toEqual(["ak", "wa"]);
  });

  it("orders by needs-review count, most first", () => {
    const rows = sortedRows({
      wa: state(10, 0, 0, 2),
      ny: state(10, 0, 0, 8),
      or: state(10, 0, 0, 5),
    });
    expect(rows.map((r) => r.code)).toEqual(["ny", "or", "wa"]);
  });
});
