import { describe, it, expect } from "vitest";
import {
  accessibleLabel,
  baselineColumnLabel,
  checkedCount,
  hasPriorScrape,
  originSourceLabel,
  sourceRowClass,
  type SourceRow,
} from "../components/review-sidebar/sidebar-model.js";
import { issueKey, type IssueChecks } from "../components/review/issue-checks.js";
import { type Issue } from "../components/review/field-model.js";

const issue = (code: string, message: string): Issue => ({ code, message }) as Issue;

const ISSUES = [
  issue("term_dates", "Mayor's term end date is before the term start date."),
  issue("missing_email", "No email address found for 3 of 7 officials."),
  issue("shared_phone", "Two council members share a phone number."),
];

const ticked = (...issues: Issue[]): IssueChecks =>
  Object.fromEntries(issues.map((i) => [issueKey(i), true]));

const row = (over: Partial<SourceRow> = {}): SourceRow => ({
  name: "Sean VanGordon",
  in_research: true,
  in_data: true,
  ...over,
});

describe("checkedCount", () => {
  it("counts only the ticked issues", () => {
    expect(checkedCount(ISSUES, {})).toBe(0);
    expect(checkedCount(ISSUES, ticked(ISSUES[0], ISSUES[2]))).toBe(2);
  });

  // Ticks are keyed by content and survive a pipeline rerun that reorders or
  // drops issues, so a tick for an issue no longer present must not be counted.
  it("ignores ticks whose issue is no longer on the card", () => {
    const stale = ticked(issue("gone", "An issue from a previous run."));
    expect(checkedCount(ISSUES, stale)).toBe(0);
  });
});

describe("accessibleLabel", () => {
  // WCAG 2.5.3: the visible label must be contained in the accessible name.
  it("spells the count out and keeps the visible label inside it", () => {
    expect(accessibleLabel(2, 5)).toBe("Checklist, 2 of 5 checked");
  });
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
  it("tints a row the research found but the data lacks as a gain", () => {
    expect(sourceRowClass(row({ in_research: true, in_data: false })))
      .toBe("review-sidebar__row--gained");
  });

  it("tints a row the data has but the research missed as a loss", () => {
    expect(sourceRowClass(row({ in_research: false, in_data: true })))
      .toBe("review-sidebar__row--lost");
  });

  // Only rows needing a decision are tinted — agreeing on both sides gets
  // nothing, and so does appearing on neither.
  it("leaves agreeing rows untinted", () => {
    expect(sourceRowClass(row({ in_research: true, in_data: true }))).toBe("");
    expect(sourceRowClass(row({ in_research: false, in_data: false }))).toBe("");
  });
});
