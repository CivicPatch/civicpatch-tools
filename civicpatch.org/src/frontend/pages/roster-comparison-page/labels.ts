import type { ComparedField, Outcome } from "./types.js";

export const OUTCOME_LABELS: Record<Outcome, string> = {
  matched: "Matched",
  possible_match: "Possible match",
  only_in_uploaded_data: "Only in uploaded data",
  only_in_civicpatch: "Only in civicpatch",
};

export const FIELD_LABELS: Record<ComparedField, string> = {
  role: "Role",
  emails: "Emails",
  phones: "Phones",
  urls: "Links",
  start_date: "Start date",
};

// One-side levels keep a ⚠: they agree, but one side knows more.
export const LEVEL_LABELS: Record<string, string> = {
  both_empty: "neither has it",
  uploaded_data_has_none: "uploaded data has none",
  civicpatch_has_none: "civicpatch has none",
  equal: "equal",
  civicpatch_has_more: "⚠ civicpatch has more",
  uploaded_data_has_more: "⚠ uploaded data has more",
  overlap: "⚠ overlap",
  differs: "differs",
  unknown: "role not recognised",
};

export const CANDIDATE_REASON_LABELS: Record<string, string> = {
  same_name: "same name",
  nickname: "nickname",
};

export function percent(part: number, whole: number): string {
  return whole === 0 ? "0%" : `${Math.round((part / whole) * 100)}%`;
}
