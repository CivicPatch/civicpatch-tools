import { ISSUE_TYPE, KNOWN_ISSUE_TYPES } from "../../utils/issue-types.js";

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

export function getIssueDetail(issueType, issueKey, data) {
  if (!data) return issueKey || "";
  if (issueType === ISSUE_TYPE.UNRECOGNIZED_ROLE) {
    const names = (data.person_names || []).join(", ");
    return names ? `${issueKey} — ${names}` : issueKey;
  }
  return issueKey;
}
