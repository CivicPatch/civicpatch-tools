import { describe, it, expect } from "vitest";
import {
  accessibleLabel,
  checkedCount,
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
