import { isChecked, type IssueChecks } from "../review/issue-checks.js";
import { type Issue } from "../review/field-model.js";

// The checklist's pure rules — the decisions that can be wrong, kept where
// vitest can reach them. It runs in a node environment, so anything asserting on
// rendered markup belongs in e2e instead. The source-table rules live with the
// component that draws them, in ../people-by-source.

export function checkedCount(issues: Issue[], checks: IssueChecks): number {
  return issues.filter((issue) => isChecked(checks, issue)).length;
}

// Spelled out, because "2/5" read aloud is meaningless. The visible label stays
// a substring of this so the accessible name still contains it (WCAG 2.5.3).
export function accessibleLabel(done: number, total: number): string {
  return `Checklist, ${done} of ${total} checked`;
}
