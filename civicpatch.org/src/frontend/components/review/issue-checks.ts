// Ticking issues off the checklist (spec §8). Pure — the storage hook lives
// with the component.
//
// A tick is personal progress, not a mutation of the card: it says "I have
// looked at this", never "this card was vetted". That is why it can persist
// client-side and stay available on a read-only card.

import { type Issue } from "./field-model.js";

export const ISSUE_CHECKS_KEY_PREFIX = "review:issue-checks:";

export const issueChecksKey = (requestId: string) =>
  `${ISSUE_CHECKS_KEY_PREFIX}${requestId}`;

// Keyed by CONTENT, not by position or person.
//
// `duplicate_unique_role` carries one message across two holders, so one tick
// correctly clears both anchors. Array position is unusable — it shifts whenever
// the issue set changes — and a generated id is worse than useless, because
// `build_review_summary` recomputes issues on every pipeline run.
//
// §8.2 specified sha256 of this string; the raw string is used instead. That
// spec was written for a database column, where length mattered. In a
// localStorage object the raw key is shorter to compute (no async
// `crypto.subtle`), cannot collide, and is legible when debugging. The property
// that matters — the key is derived from content and survives a rerun — is the
// same either way.
export const issueKey = (issue: Issue) => `${issue.code}|${issue.message}`;

export type IssueChecks = Record<string, boolean>;

export const isChecked = (checks: IssueChecks, issue: Issue) =>
  checks[issueKey(issue)] === true;

// Ticking is a toggle, and an unticked issue is simply absent rather than
// stored `false` — so the map stays the size of what the reviewer has actually
// done, and a reworded issue leaves no debris behind.
export function toggleCheck(checks: IssueChecks, issue: Issue): IssueChecks {
  const key = issueKey(issue);
  const next = { ...checks };
  if (next[key]) delete next[key];
  else next[key] = true;
  return next;
}

// Every field a ticked issue anchors to, so the rail can mark those rows
// resolved without each row re-deriving the rule.
export function resolvedFieldKeys(issues: Issue[], checks: IssueChecks): Set<string> {
  const keys = new Set<string>();
  for (const issue of issues) {
    if (issue.field && isChecked(checks, issue)) keys.add(issue.field);
  }
  return keys;
}

// Issues a card should still show. A ticked issue is done — leaving it on the
// card would mean the tick had no effect where the reviewer was looking.
export const unresolvedIssues = (issues: Issue[], checks: IssueChecks) =>
  issues.filter((issue) => !isChecked(checks, issue));
