import { describe, it, expect } from "vitest";
import { hasAnyCoverage } from "../components/progress-dashboard/freshness-widget.ts";

const tier = (fresh: number, stale: number, gap = 0, untracked = 0) => ({
  known: fresh + stale + gap + untracked,
  status_counts: { fresh, stale, gap, untracked },
});

describe("hasAnyCoverage", () => {
  it("is false when nothing has ever been scraped (most states' counties)", () => {
    expect(hasAnyCoverage(tier(0, 0, 12, 3))).toBe(false);
  });

  it("is true once at least one is fresh (Hawaii's counties)", () => {
    expect(hasAnyCoverage(tier(3, 1, 1, 0))).toBe(true);
  });

  it("is true on stale alone, not just fresh", () => {
    expect(hasAnyCoverage(tier(0, 2, 0, 0))).toBe(true);
  });
});
