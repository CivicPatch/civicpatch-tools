// What a field is, and how one compares between two records. No DOM, no I/O.
// Strictly per-FIELD — anything about a *set* of people lives in review-cards.ts.

import { type Person } from "../edit-people/person-edit-utils.js";

// Either side may be absent: no old = added, no new = the scrape didn't find them.
export type DiffRecord = Partial<Person> | null | undefined;

// Already established as present — the row assembly guards before reaching here.
export type PresentRecord = Partial<Person>;

export type FieldType = "text" | "date" | "multi" | "image";

export interface FieldSpec {
  key: string; // dotted path into a person record, e.g. "office.name"
  label: string;
  type: FieldType;
  required?: boolean; // must be non-empty; flagged when empty
  diff?: boolean; // default true; false = shown per-side but not compared
}

// Aligned to the Official data model. Jurisdiction is constant across a review,
// so it is not a per-row field.
export const FIELD_SCHEMA: FieldSpec[] = [
  // Order follows the mockup: photo, identity, office, term, contacts, sources.
  { key: "image", label: "Photo", type: "image" },
  { key: "name", label: "Name", type: "text", required: true },
  { key: "other_names", label: "Other names", type: "multi" },
  { key: "office.name", label: "Office", type: "text", required: true },
  {
    key: "office.division_ocdid",
    label: "Division",
    type: "text",
    required: true,
  },
  { key: "start_date", label: "Term start", type: "date" },
  { key: "end_date", label: "Term end", type: "date" },
  { key: "emails", label: "Email", type: "multi" },
  { key: "phones", label: "Phone", type: "multi" },
  { key: "urls", label: "Links", type: "multi" },
  { key: "source_urls", label: "Source urls", type: "multi", diff: false },
];

export function getFieldValue(person: DiffRecord, key: string): unknown {
  if (!key.includes(".")) return (person as Record<string, unknown>)?.[key];
  // Walking a dotted path is untypeable — the value changes shape each hop.
  let value: any = person;
  for (const part of key.split(".")) {
    value = value?.[part];
  }
  return value;
}

// Photo resolves cdn_image || image — cdn_image only ever exists on the old side.
export function diffValue(person: DiffRecord, field: FieldSpec): unknown {
  if (field.type === "image") return person?.cdn_image || person?.image || "";
  return getFieldValue(person, field.key);
}

// ── Scalar field diff (text / date / image) ─────────────────────────────────

export type ScalarDiffState = "same" | "changed" | "added" | "cleared";

function normalizeScalar(value: unknown): string {
  return String(value ?? "").trim();
}

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

export function normalizeMultiValue(value: string): string {
  return value.trim().toLowerCase();
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
  if (field.type === "multi") {
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

// ── Client-side validation (spec §6 — owned by the client, live) ─────────────

const DATE_PATTERN = /^\d{4}(-\d{2}(-\d{2})?)?$/;

export function isValidDate(value: string): boolean {
  return value === "" || DATE_PATTERN.test(value);
}

function padDate(value: string): string {
  const [year, month = "01", day = "01"] = value.split("-");
  return `${year}-${month}-${day}`;
}

// True when the term ordering is acceptable. Indeterminate inputs (empty or
// malformed) are not flagged here — invalid format is its own check.
export function isTermOrderValid(start: string, end: string): boolean {
  if (!start || !end || !isValidDate(start) || !isValidDate(end)) return true;
  return padDate(start) <= padDate(end);
}

// A required field with no value is an error. Multi fields count as empty when
// the list has no entries; scalars when blank after trim.
export function isRequiredFieldEmpty(record: DiffRecord, field: FieldSpec): boolean {
  if (!field.required) return false;
  const value = diffValue(record, field);
  if (Array.isArray(value)) return value.length === 0;
  return normalizeScalar(value) === "";
}

// The single client-side error for a field's value on `record`, or null. Order:
// required → date format → term ordering (end_date only).
export function fieldError(field: FieldSpec, record: DiffRecord): string | null {
  if (!record) return null;
  if (isRequiredFieldEmpty(record, field)) return "Required";
  if (field.type === "date") {
    const value = String(diffValue(record, field) ?? "");
    if (!isValidDate(value)) return "Use YYYY, YYYY-MM, or YYYY-MM-DD";
    if (
      field.key === "end_date" &&
      !isTermOrderValid(
        String(getFieldValue(record, "start_date") ?? ""),
        value,
      )
    ) {
      return "Term end is before term start";
    }
  }
  return null;
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

// A field that is never compared is context, not a change: always visible (it is
// the evidence), never a reason to review (there is no change in it).
export const isContextField = (field: FieldSpec) => field.diff === false;

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
