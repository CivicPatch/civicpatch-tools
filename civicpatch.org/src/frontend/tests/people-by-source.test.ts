import { describe, it, expect } from "vitest";
import {
  baselineColumnLabel,
  hasPriorScrape,
  originSourceLabel,
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
  // The collector only reports "existing" when it found people already in the
  // DB and skipped Gemini — the one case with a previous scrape behind it.
  it("is true only when the baseline came from existing records", () => {
    expect(hasPriorScrape("existing")).toBe(true);
    expect(hasPriorScrape("google_gemini")).toBe(false);
  });

  // A card predating origin_source, or a source we do not recognise, has not
  // proven there was a prior scrape — so it must not claim one.
  it("is false for a missing or unknown source", () => {
    expect(hasPriorScrape(null)).toBe(false);
    expect(hasPriorScrape(undefined)).toBe(false);
    expect(hasPriorScrape("some_future_model")).toBe(false);
  });
});

describe("originSourceLabel", () => {
  it("names the known sources", () => {
    expect(originSourceLabel("google_gemini")).toBe("Google Gemini");
    expect(originSourceLabel("existing")).toBe("Existing");
  });

  it("falls back rather than rendering an empty column header", () => {
    expect(originSourceLabel("some_future_model")).toBe("Research");
    expect(originSourceLabel(null)).toBe("Research");
  });
});

describe("baselineColumnLabel", () => {
  it("names the previous scrape when there was one", () => {
    expect(baselineColumnLabel("existing")).toBe("Last scrape");
  });

  // With no prior scrape the column is not a "last scrape" at all — it is
  // whatever supplied the baseline, and saying so is the point.
  it("names the source that supplied the baseline otherwise", () => {
    expect(baselineColumnLabel("google_gemini")).toBe("Google Gemini");
    expect(baselineColumnLabel(null)).toBe("Research");
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
