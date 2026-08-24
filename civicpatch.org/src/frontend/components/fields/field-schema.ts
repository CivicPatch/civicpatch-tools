// What a field *is*: the schema, and how to read one value off a record.
//
// The bottom of the field stack — it imports nothing from field-model.ts or
// field-validation.ts, so both can depend on it without a cycle. Anything that
// compares two records lives in field-model; anything that judges a value lives
// in field-validation.

import { type Person } from "../edit-people/person-edit-utils.js";

// Either side may be absent: no old = added, no new = the scrape didn't find them.
export type DiffRecord = Partial<Person> | null | undefined;

// Already established as present — the row assembly guards before reaching here.
export type PresentRecord = Partial<Person>;

export type FieldType = "text" | "date" | "multi" | "image";

// The one place each FieldType literal is written. `text` needs no predicate — it
// is what a field is when it is none of these.
export const isMulti = (field: FieldSpec) => field.type === "multi";
export const isImage = (field: FieldSpec) => field.type === "image";
export const isDate = (field: FieldSpec) => field.type === "date";

export interface FieldSpec {
  key: string; // dotted path into a person record, e.g. "office.name"
  label: string;
  type: FieldType;
  required?: boolean; // must be non-empty; flagged when empty
  diff?: boolean; // default true; false = shown per-side but not compared
}

// A field that is never compared is context, not a change: always visible (it is
// the evidence), never a reason to review (there is no change in it).
export const isContextField = (field: FieldSpec) => field.diff === false;

// Aligned to the Official data model. Jurisdiction is constant across a review,
// so it is not a per-row field.
export const FIELD_SCHEMA: FieldSpec[] = [
  // Order follows the mockup: photo, identity, office, term, contacts, sources.
  { key: "image", label: "Photo", type: "image" },
  { key: "name", label: "Name", type: "text", required: true },
  { key: "other_names", label: "Other names", type: "multi" },
  // `key` is the storage path and stays `office.*` until the proposed roster stops being
  // Official-shaped; the label is what a person reads, and posts are what we call these.
  // One field, not two: an office *is* a role and a division, so picking one sets both.
  // `key` stays `office.name` because that is still the storage path — the proposed roster is
  // Official-shaped until the pipeline contract changes.
  { key: "office.name", label: "Post", type: "text", required: true },
  { key: "start_date", label: "Term start", type: "date" },
  { key: "end_date", label: "Term end", type: "date" },
  { key: "emails", label: "Email", type: "multi" },
  { key: "phones", label: "Phone", type: "multi" },
  { key: "urls", label: "Links", type: "multi" },
  // Required: a published record with no source is unverifiable. Never compared
  // (`diff: false`) — it is the evidence, not a change.
  { key: "source_urls", label: "Source urls", type: "multi", required: true, diff: false },
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
  if (isImage(field)) return person?.cdn_image || person?.image || "";
  return getFieldValue(person, field.key);
}

// How a value is reduced before comparison. Shared rather than private to either
// consumer: the diff and the validator must agree about when two values are one,
// or a duplicate the editor flags could still read as a change.
export function normalizeScalar(value: unknown): string {
  return String(value ?? "").trim();
}

export function normalizeMultiValue(value: string): string {
  return value.trim().toLowerCase();
}
