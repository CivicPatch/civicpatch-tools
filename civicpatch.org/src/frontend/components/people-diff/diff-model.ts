// Pure diff model for the people-diff component. No DOM, no I/O — just the
// per-field diff semantics and client-side validation. Rendering and editing
// live in the component; this module is the functional core (unit-tested alone).

export type FieldType = "text" | "date" | "multi" | "image";

export interface FieldSpec {
  key: string; // dotted path into a person record, e.g. "office.name"
  label: string;
  type: FieldType;
}

// Aligned to the Official data model: office is an object, urls (not websites),
// image (not avatar), start_date/end_date. Jurisdiction is constant across a
// review (one jurisdiction per PR), so it is not an editable per-row field.
export const FIELD_SCHEMA: FieldSpec[] = [
  { key: "name", label: "Name", type: "text" },
  { key: "other_names", label: "Other names", type: "multi" },
  { key: "office.name", label: "Office", type: "text" },
  { key: "office.division_ocdid", label: "Division", type: "text" },
  { key: "start_date", label: "Term start", type: "date" },
  { key: "end_date", label: "Term end", type: "date" },
  { key: "emails", label: "Email", type: "multi" },
  { key: "phones", label: "Phone", type: "multi" },
  { key: "urls", label: "Links", type: "multi" },
  { key: "image", label: "Photo", type: "image" },
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

function normalizeMultiValue(value: string): string {
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
    result.push({ value, status: oldSet.has(normalizeMultiValue(value)) ? "both" : "added" });
  }
  for (const value of olds) {
    if (!newSet.has(normalizeMultiValue(value))) {
      result.push({ value, status: "removed" });
    }
  }
  return result;
}

// ── Record-level change (feeds computePeopleDiff's isChanged callback) ───────

export function recordsDiffer(oldRecord: any, newRecord: any): boolean {
  for (const field of FIELD_SCHEMA) {
    const oldValue = diffValue(oldRecord, field);
    const newValue = diffValue(newRecord, field);
    if (field.type === "multi") {
      const diff = multiValueDiff((oldValue as string[]) ?? [], (newValue as string[]) ?? []);
      if (diff.some((entry) => entry.status !== "both")) return true;
    } else if (fieldDiffState(oldValue, newValue, field.type) !== "same") {
      return true;
    }
  }
  return false;
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
