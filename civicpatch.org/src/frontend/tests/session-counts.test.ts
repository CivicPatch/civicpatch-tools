import { describe, expect, it } from "vitest";
import { SESSION_COUNTS, sessionCountsFor } from "../pages/review-page/session-counts.js";

describe("sessionCountsFor", () => {
  it("offers exactly what is there when it is fewer than the smallest session", () => {
    expect(sessionCountsFor(3)).toEqual([3]);
  });

  it("offers the fixed lengths once the smallest fits", () => {
    expect(sessionCountsFor(5)).toEqual(SESSION_COUNTS);
    expect(sessionCountsFor(12)).toEqual(SESSION_COUNTS);
  });

  it("offers the fixed lengths when nothing is available, since none can start", () => {
    expect(sessionCountsFor(0)).toEqual(SESSION_COUNTS);
  });
});
