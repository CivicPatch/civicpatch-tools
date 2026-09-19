import { describe, it, expect } from "vitest";
import {
  hasPriorScrape,
  sourceRowClass,
  type SourceRow,
} from "../components/people-by-source/source-model.js";

const row = (over: Partial<SourceRow> = {}): SourceRow => ({
  name: "Sean VanGordon",
  in_research: true,
  in_data: true,
  ...over,
});

describe("hasPriorScrape", () => {
  it("is true when anyone was published before this scrape", () => {
    expect(hasPriorScrape([row({ in_research: false }), row({ in_research: true })])).toBe(true);
  });

  it("is false when nobody was", () => {
    expect(hasPriorScrape([row({ in_research: false })])).toBe(false);
    expect(hasPriorScrape([])).toBe(false);
  });
});

describe("sourceRowClass", () => {
  // The same two conditions build_review_summary calls ABSENT_PERSON and
  // NEW_PERSON, so the tint has to agree with the checklist beside it.
  it("tints a name the baseline had and this scrape lost as dropped", () => {
    expect(sourceRowClass(row({ in_research: true, in_data: false })))
      .toBe("people-by-source__row--dropped");
  });

  it("tints a name only this scrape has as added", () => {
    expect(sourceRowClass(row({ in_research: false, in_data: true })))
      .toBe("people-by-source__row--added");
  });

  // Only rows needing a decision are tinted — agreeing on both sides gets
  // nothing, and so does appearing on neither.
  it("leaves agreeing rows untinted", () => {
    expect(sourceRowClass(row({ in_research: true, in_data: true }))).toBe("");
    expect(sourceRowClass(row({ in_research: false, in_data: false }))).toBe("");
  });
});
