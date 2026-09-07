import { KNOWN_ISSUE_TYPES } from "../../utils/issue-types.js";

export function getIssueTypeConfig(issueType) {
  return KNOWN_ISSUE_TYPES.find((t) => t.value === issueType);
}

export function formatIssueType(issueType) {
  return getIssueTypeConfig(issueType)?.label ?? issueType;
}

export function formatDate(isoString) {
  if (!isoString) return "";
  return new Date(isoString).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

// The stored error, for the types that record one.
export function getIssueDetail(data) {
  return data?.error ?? "";
}
