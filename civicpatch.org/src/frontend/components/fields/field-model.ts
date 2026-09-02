// How one field compares between two records, and which fields survive the
// collapse rule. No DOM, no I/O.
//
// Strictly per-FIELD — anything about a *set* of people lives in review-cards.ts.
// What a field *is* lives in field-schema.ts; whether a value is publishable
// lives in field-validation.ts. Both are re-exported here so consumers keep one
// import site (the same reason review-cards.ts re-exports Issue).

import {
  FIELD_SCHEMA,
  diffValue,
  isContextField,
  isMulti,
  normalizeMultiValue,
  normalizeScalar,
  type DiffRecord,
  type FieldSpec,
  type FieldType,
} from "./field-schema.js";
import { fieldError } from "./field-validation.js";

export * from "./field-schema.js";
export * from "./field-validation.js";

// ── Scalar field diff (text / date / image) ─────────────────────────────────

export type ScalarDiffState = "same" | "changed" | "added" | "cleared";

export function fieldDiffState(
  oldValue: unknown,
  newValue: unknown,
  type: FieldType,
): ScalarDiffState {
  const oldStr = normalizeScalar(oldValue);
  const newStr = normalizeScalar(newValue);
  // Presence only: old is a CDN copy and new a raw scrape, so the URLs differ
  // even when the photo has not.
  if (type === "image") {
    if (!!oldStr === !!newStr) return "same";
    return newStr ? "added" : "cleared";
  }
  if (oldStr === newStr) return "same";
  if (!oldStr) return "added";
  if (!newStr) return "cleared";
  return "changed";
}

// ── Multi-value field diff (emails / phones / urls / other_names) ────────────

export type MultiValueStatus = "both" | "added" | "removed";
export interface MultiValueDiff {
  value: string;
  status: MultiValueStatus;
}

// New values first (in their given order), then old-only values flagged removed.
export function multiValueDiff(
  oldValues: string[],
  newValues: string[],
): MultiValueDiff[] {
  const olds = oldValues ?? [];
  const news = newValues ?? [];
  const oldSet = new Set(olds.map(normalizeMultiValue));
  const newSet = new Set(news.map(normalizeMultiValue));

  const result: MultiValueDiff[] = [];
  for (const value of news) {
    result.push({
      value,
      status: oldSet.has(normalizeMultiValue(value)) ? "both" : "added",
    });
  }
  for (const value of olds) {
    if (!newSet.has(normalizeMultiValue(value))) {
      result.push({ value, status: "removed" });
    }
  }
  return result;
}

// The whole-field verdict for a multi-value field, collapsing its per-value diff:
// values on both sides only = same, gains only = added, losses only = cleared,
// both = changed.
export function multiValueState(
  oldValues: string[],
  newValues: string[],
): ScalarDiffState {
  const diff = multiValueDiff(oldValues, newValues);
  const gained = diff.some((entry) => entry.status === "added");
  const lost = diff.some((entry) => entry.status === "removed");
  if (gained && lost) return "changed";
  if (gained) return "added";
  if (lost) return "cleared";
  return "same";
}

// ── Field- and record-level change ───────────────────────────────────────────

// One field's verdict, dispatching on its type. `diff: false` fields
// (source_urls) are documentation and never compare.
export function fieldState(
  field: FieldSpec,
  oldRecord: DiffRecord,
  newRecord: DiffRecord,
): ScalarDiffState {
  if (field.diff === false) return "same";
  const oldValue = diffValue(oldRecord, field);
  const newValue = diffValue(newRecord, field);
  if (isMulti(field)) {
    return multiValueState(
      (oldValue as string[]) ?? [],
      (newValue as string[]) ?? [],
    );
  }
  return fieldDiffState(oldValue, newValue, field.type);
}

export type FieldChangeState = Exclude<ScalarDiffState, "same">;

export interface FieldChange {
  field: FieldSpec;
  state: FieldChangeState;
}

// Every field that actually differs, in schema order. Callers that only need
// "did anything change?" use recordsDiffer, which is this same traversal — so
// the person-level and field-level answers can never disagree.
export function changedFields(
  oldRecord: DiffRecord,
  newRecord: DiffRecord,
): FieldChange[] {
  const changes: FieldChange[] = [];
  for (const field of FIELD_SCHEMA) {
    const state = fieldState(field, oldRecord, newRecord);
    if (state !== "same") changes.push({ field, state });
  }
  return changes;
}

// Feeds computePeopleDiff's isChanged callback.
export function recordsDiffer(
  oldRecord: DiffRecord,
  newRecord: DiffRecord,
): boolean {
  return changedFields(oldRecord, newRecord).length > 0;
}

// ── Reviewer issues ──────────────────────────────────────────────────────────

// Lives here because the collapse rule reads it; grouping by person is card-level.
export interface Issue {
  code: string;
  message: string;
  person_ids?: string[];
  field?: string | null;
}

// ── The collapse rule (§2) ───────────────────────────────────────────────────

// Ordered by how much it demands of the reviewer, and that order is the
// precedence when several apply.
export type FieldReason = "error" | "issue" | "diff" | "context";

export interface SurvivingField {
  field: FieldSpec;
  state: ScalarDiffState;
  reason: FieldReason;
  error: string | null;
}

// What a card shows before expanding. The error clause is not redundant: a
// required field empty on BOTH sides reads `same` and still blocks publish.
//
// Ranked last, so a real error or issue on the same field still wins the badge.
export function survivingFields(
  oldRecord: DiffRecord,
  newRecord: DiffRecord,
  issues: Issue[] = [],
): SurvivingField[] {
  const anchoredFields = new Set(
    issues.map((issue) => issue.field).filter(Boolean) as string[],
  );

  const surviving: SurvivingField[] = [];
  for (const field of FIELD_SCHEMA) {
    const state = fieldState(field, oldRecord, newRecord);
    const error = fieldError(field, newRecord);
    const reason: FieldReason | null = error
      ? "error"
      : anchoredFields.has(field.key)
        ? "issue"
        : state !== "same"
          ? "diff"
          : isContextField(field)
            ? "context"
            : null;
    if (reason) surviving.push({ field, state, reason, error });
  }
  return surviving;
}

// One issue can name several people, so it lands on each of their cards.
