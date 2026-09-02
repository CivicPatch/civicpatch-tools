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
  key: string; // the field on a person record
  label: string;
  type: FieldType;
  required?: boolean; // must be non-empty; flagged when empty
  diff?: boolean; // default true; false = shown per-side but not compared
  context?: boolean; // default false; true = always visible, never a reason to review
}

// Two separate questions, and they were one flag until a photo needed to answer them
// differently. `diff: false` says "do not compare this" — a photo moving is not a change a
// reviewer decides about. `context: true` says "always show this" — source urls are the
// evidence, so they are visible whether or not anything moved. Source urls want both; a photo
// wants only the first, or every row would list "Photo" as a surviving field.
export const isContextField = (field: FieldSpec) => field.context === true;

// Mirrors `POST_FIELD` in shared/schemas.py — the key an issue about a person's post anchors
// to, and the one field whose two sides are not both read off the record.
export const POST_FIELD = "post_id";

// Aligned to the Official data model. Jurisdiction is constant across a review,
// so it is not a per-row field.
export const FIELD_SCHEMA: FieldSpec[] = [
  // Order follows the mockup: photo, identity, post, term, contacts, sources.
  // Not compared (`diff: false`): a photo moving — a new crop, a CDN rehost, the same
  // face from a different url — is not something a reviewer needs to decide about, and
  // making it one opened a card for every person whose image url merely changed.
  { key: "image", label: "Photo", type: "image", diff: false },
  { key: "name", label: "Name", type: "text", required: true },
  { key: "other_names", label: "Other names", type: "multi" },
  // A post is picked, not typed. Not `required: true` — the pipeline never sets `post_id`;
  // `fieldError` asks only when nothing can derive one.
  //
  // NOT `labels`. Those are what the source said — evidence, never edited — and putting them
  // here showed a person named twice by one page as two entries in the Post field, which reads
  // as a duplicate because it is two spellings of one answer.
  { key: "post_id", label: "Post", type: "text" },
  { key: "start_date", label: "Term start", type: "date" },
  { key: "end_date", label: "Term end", type: "date" },
  { key: "emails", label: "Email", type: "multi" },
  { key: "phones", label: "Phone", type: "multi" },
  { key: "urls", label: "Links", type: "multi" },
  // Required: a published record with no source is unverifiable. Never compared
  // (`diff: false`) — it is the evidence, not a change.
  { key: "source_urls", label: "Source urls", type: "multi", required: true, diff: false, context: true },
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
