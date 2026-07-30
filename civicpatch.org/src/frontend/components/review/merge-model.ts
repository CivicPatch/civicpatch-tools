// Merging two people into one. Pure — no DOM, no state. The picker renders a
// plan and toggles choices on it; nothing here knows that a picker exists.
//
// Replaces the *policy* in `mergeFields`, not the plumbing: the absorbed person
// simply leaves `currentPeople`, and `buildPeoplePatch` already reads that as a
// deletion.

import {
  FIELD_SCHEMA,
  getFieldValue,
  type DiffRecord,
  type FieldSpec,
  type PresentRecord,
} from "./field-model.js";
import { RailStatus, type ReviewCard } from "./review-cards.js";

// `keep` — the survivor's value stands. `replace` — the candidate's wins.
// `both` — union for a list, deduped join for an office name.
export const MergeChoice = Object.freeze({
  KEEP: "keep",
  REPLACE: "replace",
  BOTH: "both",
});

export type MergeChoiceKey = (typeof MergeChoice)[keyof typeof MergeChoice];

export interface MergeFieldPlan {
  field: FieldSpec;
  survivorValue: unknown;
  candidateValue: unknown;
  same: boolean;
  choices: MergeChoiceKey[]; // which buttons this field offers
  choice: MergeChoiceKey; // the pre-pressed default
}

export interface MergePlan {
  survivorId: string;
  absorbedId: string;
  fields: MergeFieldPlan[];
}

const OFFICE_NAME_SEPARATOR = " - ";
const OFFICE_NAME_KEY = "office.name";

// Two fields are never a choice. Aliases are what make a merge durable —
// matching consults them, so the absorbed name resolves to the survivor on the
// next scrape, and a reviewer tidying the list could silently un-merge the pair.
// Sources are documentation, never compared; offering a control over provenance
// only invites fiddling with it.
const ALWAYS_UNION = new Set(["other_names", "source_urls"]);

// A person the reviewer has already decided about is not a candidate: "drop this
// person" and "keep parts of this person" are contradictory answers to the same
// question, so those two states simply do not offer it.
const DECIDED = new Set<string>([RailStatus.DELETED, RailStatus.RESTORED]);

export function canMerge(card: ReviewCard): boolean {
  return !DECIDED.has(card.status);
}

// Everyone else on the card who is still an open question.
export function mergeCandidates(anchor: ReviewCard, cards: ReviewCard[]): ReviewCard[] {
  return cards.filter((card) => card.personId !== anchor.personId && canMerge(card));
}

// ── Survivor ─────────────────────────────────────────────────────────────────

// The record a card is currently editing. A person the scrape didn't find has
// only an old side.
export function liveRecord(card: ReviewCard): DiffRecord {
  return card.newRecord ?? card.oldRecord;
}

// First match wins. Scraped ids are ephemeral — resolve_people_ids mints a fresh
// uuid4 for anything it cannot match — so a record already in the database
// always outranks one that is not.
export function chooseSurvivor(a: ReviewCard, b: ReviewCard): ReviewCard {
  const inDatabase = (card: ReviewCard) => card.oldRecord != null;
  if (inDatabase(a) !== inDatabase(b)) return inDatabase(a) ? a : b;

  // Both durable (or neither): prefer the one this scrape still matched.
  const matched = (card: ReviewCard) => card.newRecord != null;
  if (matched(a) !== matched(b)) return matched(a) ? a : b;

  return a; // caller passes them in frozen order, so `a` is the earlier row
}

// ── Values ───────────────────────────────────────────────────────────────────

function isEmpty(value: unknown): boolean {
  if (value == null) return true;
  if (Array.isArray(value)) return value.length === 0;
  return String(value).trim() === "";
}

function asList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter(Boolean).map(String) : [];
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}

const isMulti = (field: FieldSpec) => field.type === "multi";

// A photo is stored as a CDN copy on the old side and a raw scrape URL on the
// new one, so the comparable value is whichever is present.
function readValue(record: DiffRecord, field: FieldSpec): unknown {
  if (field.type === "image") {
    return (record as any)?.cdn_image || (record as any)?.image || "";
  }
  return getFieldValue(record, field.key);
}

// Two office names combine by splitting on the separator, deduping the parts and
// rejoining. Without the dedupe two merged Mayors become "Mayor - Mayor", which
// _check_duplicate_unique_roles reads back as two holders and flags the merged
// person as duplicating a role with themselves.
export function joinOfficeNames(survivor: unknown, candidate: unknown): string {
  const parts = [String(survivor ?? ""), String(candidate ?? "")]
    .flatMap((name) => name.split(OFFICE_NAME_SEPARATOR))
    .map((part) => part.trim())
    .filter(Boolean);
  return unique(parts).join(OFFICE_NAME_SEPARATOR);
}

function valuesMatch(field: FieldSpec, survivor: unknown, candidate: unknown): boolean {
  if (isMulti(field)) {
    const a = unique(asList(survivor)).sort();
    const b = unique(asList(candidate)).sort();
    return a.length === b.length && a.every((value, i) => value === b[i]);
  }
  return String(survivor ?? "").trim() === String(candidate ?? "").trim();
}

// ── Plan ─────────────────────────────────────────────────────────────────────

function choicesFor(field: FieldSpec): MergeChoiceKey[] {
  if (ALWAYS_UNION.has(field.key)) return [MergeChoice.BOTH];
  if (isMulti(field)) return [MergeChoice.KEEP, MergeChoice.BOTH];
  if (field.key === OFFICE_NAME_KEY) {
    return [MergeChoice.KEEP, MergeChoice.REPLACE, MergeChoice.BOTH];
  }
  return [MergeChoice.KEEP, MergeChoice.REPLACE];
}

// Pre-pressed to the link result — the candidate's values win — but only when the
// candidate is a fresh scrape with no database history. Two records that both
// exist are both curated, so neither is the obvious winner and the survivor
// keeps what it has. An empty candidate never displaces a filled survivor.
function defaultChoice(
  field: FieldSpec,
  candidateValue: unknown,
  candidateIsScraped: boolean,
): MergeChoiceKey {
  if (isMulti(field)) return MergeChoice.BOTH;
  if (!candidateIsScraped) return MergeChoice.KEEP;
  return isEmpty(candidateValue) ? MergeChoice.KEEP : MergeChoice.REPLACE;
}

export function planMerge(survivor: ReviewCard, candidate: ReviewCard): MergePlan {
  const survivorRecord = liveRecord(survivor);
  const candidateRecord = liveRecord(candidate);

  // No old side means the scrape found them and the database has never seen them.
  const candidateIsScraped = candidate.oldRecord == null;

  const fields = FIELD_SCHEMA.map((field) => {
    const survivorValue = readValue(survivorRecord, field);
    const candidateValue = readValue(candidateRecord, field);
    const same = valuesMatch(field, survivorValue, candidateValue);
    return {
      field,
      survivorValue,
      candidateValue,
      same,
      choices: choicesFor(field),
      choice: same
        ? choicesFor(field)[0]
        : defaultChoice(field, candidateValue, candidateIsScraped),
    };
  });

  return {
    survivorId: survivor.personId,
    absorbedId: candidate.personId,
    fields,
  };
}

// Ignores a choice the field does not offer. Without this, `both` on a date
// reaches the office-name join and produces "2023-01-03 - 2023-01-01".
export function setChoice(
  plan: MergePlan,
  fieldKey: string,
  choice: MergeChoiceKey,
): MergePlan {
  return {
    ...plan,
    fields: plan.fields.map((entry) =>
      entry.field.key === fieldKey && entry.choices.includes(choice)
        ? { ...entry, choice }
        : entry,
    ),
  };
}

// ── Apply ────────────────────────────────────────────────────────────────────

function writeValue(record: any, key: string, value: unknown): void {
  if (!key.includes(".")) {
    record[key] = value;
    return;
  }
  const [head, ...rest] = key.split(".");
  record[head] = { ...(record[head] ?? {}) };
  writeValue(record[head], rest.join("."), value);
}

function resolve(entry: MergeFieldPlan): unknown {
  const { field, choice, survivorValue, candidateValue } = entry;
  if (choice === MergeChoice.KEEP) return survivorValue;
  if (choice === MergeChoice.REPLACE) return candidateValue;
  if (isMulti(field)) return unique([...asList(survivorValue), ...asList(candidateValue)]);
  return joinOfficeNames(survivorValue, candidateValue);
}

// A displaced name is never lost — it becomes an alias, which is what
// `other_names` is for, and what mergeFields already does.
function foldAliases(merged: any, survivorName: unknown, candidateName: unknown): void {
  const primary = String(merged.name ?? "").trim();
  const aliases = unique([
    ...asList(merged.other_names),
    String(survivorName ?? "").trim(),
    String(candidateName ?? "").trim(),
  ]);
  merged.other_names = aliases.filter((alias) => alias && alias !== primary);
}

// Two records combined with nothing overridden — the reviewer asserting the pair
// is one human and accepting the defaults. This is what the retired "link to
// person" did; merge is this call with a plan the reviewer has edited.
export function mergeCards(survivor: ReviewCard, candidate: ReviewCard): PresentRecord {
  return applyMergePlan(planMerge(survivor, candidate), survivor, candidate);
}

// The merged person: the survivor's id, the plan's values. The absorbed record is
// dropped by the caller — publish reads its absence as a deletion.
export function applyMergePlan(
  plan: MergePlan,
  survivor: ReviewCard,
  candidate: ReviewCard,
): PresentRecord {
  const survivorRecord = (liveRecord(survivor) ?? {}) as any;
  const candidateRecord = (liveRecord(candidate) ?? {}) as any;
  const merged: any = { ...survivorRecord, id: plan.survivorId };

  for (const entry of plan.fields) {
    if (entry.field.type === "image") {
      // The old side's value is a CDN copy of a URL the scrape no longer serves,
      // so a replaced photo is written raw and the stale copy dropped.
      const value = resolve(entry);
      if (entry.choice === MergeChoice.REPLACE) {
        merged.image = value;
        merged.cdn_image = null;
      }
      continue;
    }
    writeValue(merged, entry.field.key, resolve(entry));
  }

  foldAliases(merged, survivorRecord.name, candidateRecord.name);

  // Everything outside FIELD_SCHEMA comes from the survivor by the spread above.
  // That is right for jurisdiction_ocdid, which cannot differ — the card is
  // scoped to one jurisdiction — but wrong for a timestamp, where the merged
  // record should not look older than the data it just absorbed.
  const timestamps = [survivorRecord.updated_at, candidateRecord.updated_at].filter(Boolean);
  if (timestamps.length) merged.updated_at = timestamps.sort().at(-1);

  return merged as PresentRecord;
}
