import { describe, it, expect } from "vitest";
import { reviewsReady } from "../pages/review-session-page/review-progress.ts";

describe("reviewsReady", () => {
  it("is the whole available pool when well under goal", () => {
    expect(reviewsReady(5, 10, 0)).toBe(5);
  });

  it("counts down by one per review as the available pool shrinks", () => {
    // Each publish merges a PR out of `available` (−1) and bumps resolved (+1).
    expect(reviewsReady(4, 10, 1)).toBe(4);
    expect(reviewsReady(3, 10, 2)).toBe(3);
    expect(reviewsReady(2, 10, 3)).toBe(2);
  });

  it("does not double-subtract today_resolved (regression: the old min(avail,goal)-resolved bug)", () => {
    // Old formula gave min(2,10)-3 = 0 while 2 PRs were still available.
    expect(reviewsReady(2, 10, 3)).toBe(2);
  });

  it("is capped by the remaining goal when more are available than needed", () => {
    expect(reviewsReady(20, 10, 0)).toBe(10);
    expect(reviewsReady(20, 10, 3)).toBe(7);
  });

  it("is zero once the goal is met or exceeded", () => {
    expect(reviewsReady(5, 10, 10)).toBe(0);
    expect(reviewsReady(5, 10, 12)).toBe(0);
  });

  it("is zero when nothing is available", () => {
    expect(reviewsReady(0, 10, 0)).toBe(0);
  });
});
