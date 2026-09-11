import { describe, it, expect } from "vitest";
import { reviewCountSuffix, verbFor } from "../pages/home-page/recent-publications.js";

describe("reviewCountSuffix", () => {
  it("is silent for a single update — the sentence already names who made it", () => {
    expect(reviewCountSuffix(1)).toBe("");
  });

  it("counts the updates when there's more than one", () => {
    expect(reviewCountSuffix(3)).toBe("(3 updates)");
  });
});

describe("verbFor", () => {
  it("names a reviewer-approved scrape a review", () => {
    expect(verbFor("scrape")).toBe("published a review of");
  });

  it("names a hand edit an edit, not a review", () => {
    expect(verbFor("people_edit")).toBe("edited");
  });

  it("names a rollback", () => {
    expect(verbFor("rollback")).toBe("rolled back changes to");
  });

  it("falls back to a generic verb for an unrecognized or missing kind", () => {
    expect(verbFor("something_new")).toBe("updated");
    expect(verbFor(null)).toBe("updated");
  });
});
