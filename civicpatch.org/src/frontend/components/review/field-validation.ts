// Client-side validation (spec §6 — owned by the client, live).
//
// One question: is this value publishable? Nothing here compares two records —
// that is field-model.ts. Mirrors the rules Official enforces on publish
// (shared/schemas.py), so the reviewer hears about a problem while typing rather
// than as a failed Publish. Where it differs it is deliberately *stricter*: being
// stricter costs a typo, being looser costs a failed publish.

import { DISTRICT_TYPES } from "../edit-people/person-edit-utils.js";
import {
  diffValue,
  getFieldValue,
  isDate,
  isMulti,
  normalizeMultiValue,
  normalizeScalar,
  type DiffRecord,
  type FieldSpec,
} from "./field-schema.js";

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

// Mirrors Official.validate_urls (shared/schemas.py), the rule publish runs
// against. Case-sensitive on the scheme because the backend's startswith is.
// Stricter than the backend on whitespace only — urlparse accepts a space.
//
// Exported because the jurisdiction page's Website field is a url that never
// reaches a FieldSpec: it patches the jurisdictions repo, not a person, so it
// has no VALUE_ERRORS entry to find. One rule, both places.
export const urlError = (text: string) => {
  if (!text.startsWith("http://") && !text.startsWith("https://")) {
    return `${text} must start with http:// or https://`;
  }
  if (/\s/.test(text)) return `${text} cannot contain spaces`;
  const host = text.split("//")[1]?.split(/[/?#]/)[0] ?? "";
  return host.includes(".") ? null : `${text} needs a domain, like example.gov`;
};

// Only the district number is typed — the base comes from the jurisdiction. The
// type select saves the moment it changes, so picking one and typing nothing
// leaves a dangling "council_district:" that reads back as a valid selection.
const divisionError = (text: string) => {
  const lastSegment = text.split("/").pop() ?? "";
  const colon = lastSegment.indexOf(":");
  if (colon === -1) return null;
  const label = lastSegment.slice(0, colon);
  if (!DISTRICT_TYPES.includes(label)) return null;

  const name = label.replace("_", " ");
  const value = lastSegment.slice(colon + 1);
  if (!value) return `Enter a ${name} number`;
  return /\s/.test(value) ? `${name} number cannot contain spaces` : null;
};

// Per-value format checks, by field. Deliberately permissive: the backend
// canonicalises and is the authority (shared/schemas.py), so this catches only
// what it would certainly reject. A field with no entry here has no format to
// violate.
const VALUE_ERRORS: Record<string, (text: string) => string | null> = {
  phones: (text) => {
    // An extension is not part of the number.
    const digits = text.split(/\bext\.?\b|\bx\b/i)[0].replace(/\D/g, "");
    const national = digits.startsWith("1") ? digits.slice(1) : digits;
    return national.length === 10 ? null : `${text} is not a 10-digit US number`;
  },
  emails: (text) =>
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text) ? null : `${text} is not a valid email`,
  urls: urlError,
  source_urls: urlError,
  "office.division_ocdid": divisionError,
};

// One value of a field, or null if it is fine. Multi fields call it per row (the
// editor marks the offending row, not the whole field); scalar fields call it
// once with their whole value. One definition of valid for both.
export function valueError(field: FieldSpec, value: string): string | null {
  const text = String(value ?? "").trim();
  if (!text) return null;
  return VALUE_ERRORS[field.key]?.(text) ?? null;
}

// buildPeoplePatch sends blank rows as-is, and Official treats them unevenly:
// validate_phones and validate_urls skip them, validate_emails matches "" against
// its pattern and raises. So a blank is only worth flagging for emails.
const BLANK_REJECTED = new Set(["emails"]);

// One row of a multi-value field. Unlike valueError it sees the whole list and
// the record, which is what a duplicate — or a nickname that is already the name
// — can only be judged against. Exported for the same reason valueError is: the
// editor marks the offending row, and both must agree on which one that is.
export function rowError(
  field: FieldSpec,
  values: string[],
  index: number,
  record: DiffRecord,
): string | null {
  const text = String(values[index] ?? "").trim();
  // A cleared row, not the trailing "add" slot — that one is never in `values`.
  // Only an error where publish would actually fail on it.
  if (!text) return BLANK_REJECTED.has(field.key) ? "Remove the empty row" : null;

  const format = valueError(field, text);
  if (format) return format;

  // Compared the way the diff compares, so case alone is not a second value.
  const normalized = normalizeMultiValue(text);
  const earlier = values.slice(0, index);
  if (earlier.some((value) => normalizeMultiValue(value) === normalized)) {
    return `${text} is listed twice`;
  }

  if (field.key === "other_names") {
    const name = normalizeMultiValue(String(getFieldValue(record, "name") ?? ""));
    if (name && normalized === name) return `${text} is already the name`;
  }
  return null;
}

// The single client-side error for a field's value on `record`, or null. Order:
// required → date format → term ordering (end_date only) → value format.
export function fieldError(field: FieldSpec, record: DiffRecord): string | null {
  if (!record) return null;
  if (isRequiredFieldEmpty(record, field)) return "Required";
  if (isMulti(field)) {
    const values = (diffValue(record, field) as string[]) ?? [];
    for (let index = 0; index < values.length; index++) {
      const error = rowError(field, values, index, record);
      if (error) return error;
    }
    return null;
  }
  if (isDate(field)) {
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
    return null;
  }
  return valueError(field, String(diffValue(record, field) ?? ""));
}
