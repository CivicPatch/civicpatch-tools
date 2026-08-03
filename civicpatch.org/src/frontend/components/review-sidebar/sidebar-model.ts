import { isChecked, type IssueChecks } from "../review/issue-checks.js";
import { type Issue } from "../review/field-model.js";

// The drawer's pure rules — the decisions that can be wrong, kept where vitest
// can reach them. It runs in a node environment, so anything asserting on
// rendered markup belongs in e2e instead.

export function checkedCount(issues: Issue[], checks: IssueChecks): number {
  return issues.filter((issue) => isChecked(checks, issue)).length;
}

// Spelled out, because "2/5" read aloud is meaningless. The visible label stays
// a substring of this so the accessible name still contains it (WCAG 2.5.3).
export function accessibleLabel(done: number, total: number): string {
  return `Checklist, ${done} of ${total} checked`;
}

const EXISTING_SOURCE = "existing";

const ORIGIN_SOURCE_LABEL_BY_KEY: Record<string, string> = {
  google_gemini: "Google Gemini",
  [EXISTING_SOURCE]: "Existing",
};

// origin_source says where the comparison's baseline came from. The collector
// uses people already in the DB when it finds any, and skips Gemini — so
// "existing" is the only value that means there was a previous scrape to
// compare against. Anything else and Gemini supplied the baseline itself, which
// makes the table a first capture rather than a diff.
export function hasPriorScrape(originSource: string | null | undefined): boolean {
  return originSource === EXISTING_SOURCE;
}

// A pipeline that grows a new origin source should still render a usable column
// header rather than an empty one.
export function originSourceLabel(originSource: string | null | undefined): string {
  return (originSource && ORIGIN_SOURCE_LABEL_BY_KEY[originSource]) || "Research";
}

// The baseline side of the comparison: the previous scrape when there was one,
// otherwise whatever supplied the baseline instead.
export function baselineColumnLabel(originSource: string | null | undefined): string {
  return hasPriorScrape(originSource) ? "Last scrape" : originSourceLabel(originSource);
}

export interface SourceRow {
  name: string;
  in_research: boolean;
  in_data: boolean;
}

// Green where the research found someone the data does not have — a gain. Red
// where the data has someone the research did not find — a loss. Agreeing on
// both sides gets nothing, so only rows needing a decision are tinted.
export function sourceRowClass(row: SourceRow): string {
  if (row.in_research && !row.in_data) return "review-sidebar__row--gained";
  if (!row.in_research && row.in_data) return "review-sidebar__row--lost";
  return "";
}
