import { describe, it, expect } from "vitest";
import { reviewCountSuffix, verbFor } from "../pages/home-page/recent-publications.js";

describe("reviewCountSuffix", () => {
  it("is silent for a single update — only multiples need a count annotation", () => {
    expect(reviewCountSuffix(1)).toBe("");
  });

  it("counts the updates when there's more than one", () => {
    expect(reviewCountSuffix(3)).toBe("(3 updates)");
  });
});

// Passive, not "X imported data for" — the public feed carries no author (see
// schemas/activity.py::PublicPublication), so the jurisdiction is the sentence's
// subject and the verb has to read as something that happened to it.
describe("verbFor", () => {
  it("names a reviewer-approved scrape a review", () => {
    expect(verbFor("scrape")).toBe("was published");
  });

  it("names a hand edit an edit, not a review", () => {
    expect(verbFor("people_edit")).toBe("was edited");
  });

  it("names a rollback", () => {
    expect(verbFor("rollback")).toBe("had changes rolled back");
  });

  it("falls back to a generic verb for an unrecognized or missing kind", () => {
    expect(verbFor("something_new")).toBe("was updated");
    expect(verbFor(null)).toBe("was updated");
  });
});
