// Pure diff model for the people-diff component. No DOM, no I/O — just the
// per-field diff semantics and client-side validation. Rendering and editing
// live in the component; this module is the functional core (unit-tested alone).

import { type Person } from "../edit-people/person-edit-utils.js";

// Either side of a diff. The old side may be absent (an added person) and the
// new side may be absent (one the scrape didn't find). Partial because the diff
// only ever reads field values — it never needs a person to be whole, or to
// carry an id.
export type DiffRecord = Partial<Person> | null | undefined;

export type FieldType = "text" | "date" | "multi" | "image";

export interface FieldSpec {
  key: string; // dotted path into a person record, e.g. "office.name"
  label: string;
  type: FieldType;
  required?: boolean; // must be non-empty; flagged when empty
  diff?: boolean; // default true; false = shown per-side but not compared
}

// Aligned to the Official data model: office is an object, urls (not websites),
// image (not avatar), start_date/end_date. Jurisdiction is constant across a
// review (one jurisdiction per PR), so it is not an editable per-row field.
// Required fields render always; optional fields collapse when unchanged.
// source_urls is documentation — shown per-side, never diffed (each list has
// its own sources). Division is edited as a seat-type + number (see component).
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

export function getFieldValue(person: any, key: string): unknown {
  if (!key.includes(".")) return person?.[key];
  let value = person;
  for (const part of key.split(".")) {
    value = value?.[part];
  }
  return value;
}

// The value to diff/display for a field. For the photo, the effective URL is
// cdn_image || image: cdn_image is only ever present on the OLD side (a scrape
// produces only `image`), so this resolves correctly on either side.
export function diffValue(person: any, field: FieldSpec): unknown {
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
  // Photos diff on presence only — the URLs aren't comparable (old=CDN copy,
  // new=raw scrape), so two valid photos are never "changed", just present.
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
export function isRequiredFieldEmpty(record: any, field: FieldSpec): boolean {
  if (!field.required) return false;
  const value = diffValue(record, field);
  if (Array.isArray(value)) return value.length === 0;
  return normalizeScalar(value) === "";
}

// The single client-side error for a field's value on `record`, or null. Order:
// required → date format → term ordering (end_date only).
export function fieldError(field: FieldSpec, record: any): string | null {
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

// ── Linking an added person to an existing record ────────────────────────────

// "Link to person": an unmatched scraped person (an `added` row) is actually an
// existing old-side record. The scraped person adopts the existing id, so on
// publish it overlays that record by id instead of inserting a duplicate (the
// reviewer keeps the scraped fields). The existing person's name and aliases fold
// into other_names so the *next* scrape resolves by alias instead of re-proposing
// the same person.
export function buildLinkUpdates(
  added: any,
  target: any,
): { id: string; other_names: string[] } {
  // The target's old name and both sides' aliases all become aliases of the
  // linked record — deduped, minus blanks and the added person's own name
  // (which stays the primary name).
  const candidates = [
    target?.name,
    ...(target?.other_names ?? []),
    ...(added?.other_names ?? []),
  ];
  const other_names = [...new Set(candidates)].filter(
    (alias) => alias && alias !== added?.name,
  );
  return { id: target.id, other_names };
}

// ── Reviewer issues → per-card anchoring ─────────────────────────────────────

// A reviewer-facing issue from build_review_summary. Only person-anchored issues
// (non-empty person_ids) mark a card; list-level issues stay in the checklist.
// Legacy migrated issues carry only a message, hence the optionals.
export interface Issue {
  code: string;
  message: string;
  person_ids?: string[];
  field?: string | null;
}

// Group person-anchored issues by the card (person id) they mark. One issue can
// name several holders (e.g. a duplicated unique role), so it lands on each.
export function indexIssuesByPersonId(issues: Issue[]): Map<string, Issue[]> {
  const byId = new Map<string, Issue[]>();
  for (const issue of issues) {
    for (const id of issue.person_ids ?? []) {
      const list = byId.get(id) ?? [];
      list.push(issue);
      byId.set(id, list);
    }
  }
  return byId;
}
