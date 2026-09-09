import { describe, it, expect } from "vitest";
import { reviewLabel } from "../pages/home-page/recent-publications.js";

describe("reviewLabel", () => {
  it("names the reviewer for a single review", () => {
    expect(reviewLabel({ author_name: "michelle", review_count: 1 })).toBe(
      "reviewed by michelle",
    );
  });

  it("counts and names only the latest reviewer for more than one", () => {
    expect(reviewLabel({ author_name: "michelle", review_count: 3 })).toBe(
      "reviewed 3 times, most recently by michelle",
    );
  });
});
