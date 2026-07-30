// One card per person: what happened to them, and which fields survive the
// collapse rule. Pure — the rail and useFrozenFields read the same answer.

import { computePeopleDiff, DiffType } from "../../utils/diff-utils.js";
import {
  FIELD_SCHEMA,
  fieldError,
  isContextField,
  recordsDiffer,
  survivingFields,
  type DiffRecord,
  type Issue,
  type SurvivingField,
} from "./field-model.js";
import {
  parseDivision,
  DIVISION_AT_LARGE,
} from "../edit-people/person-edit-utils.js";

// `deleted` and `restored` are reviewer decisions, not diff verdicts — hence not
// DiffType values.
export const RailStatus = Object.freeze({
  CHANGED: "changed",
  ADDED: "added",
  UNCHANGED: "unchanged",
  REMOVED: "removed",
  DELETED: "deleted",
  RESTORED: "restored",
});

export type RailStatusKey = (typeof RailStatus)[keyof typeof RailStatus];

// Each label names its actor: "removed" and "deleted" are synonyms in English but
// mean different things here, so neither bare word is ever UI copy.
export const STATUS_LABEL: Record<RailStatusKey, string> = {
  [RailStatus.CHANGED]: "changed",
  [RailStatus.ADDED]: "new",
  [RailStatus.UNCHANGED]: "unchanged",
  [RailStatus.REMOVED]: "not found in scrape",
  [RailStatus.DELETED]: "you removed",
  [RailStatus.RESTORED]: "restored",
};

// Both routes out of the roster. They render identically — who caused it is in
// the banner, not the styling.
export const DEPARTING = new Set<string>([RailStatus.REMOVED, RailStatus.DELETED]);

// "Council President · Ward 9" — shared by Overview's tiles and the modal's list.
export function cardSubtitle(
  card: ReviewCard,
  toFriendlyDivision: (ocdid: string) => string,
): string {
  const record = personOf(card);
  const office = record?.office?.name ?? "";
  const division = toFriendlyDivision(record?.office?.division_ocdid ?? "") || "";
  return [office, division].filter(Boolean).join(" · ");
}

// The new side is live; someone the scrape didn't find has only the old side.
export const personOf = (card: ReviewCard) => card.newRecord ?? card.oldRecord;

export interface CardsResult {
  cards: ReviewCard[];
  duplicateIds: string[];
}

export interface ReviewCard {
  personId: string;
  status: RailStatusKey;
  oldRecord: DiffRecord;
  newRecord: DiffRecord;
  surviving: SurvivingField[];
  issues: Issue[];
}

export interface BuildCardsInput {
  existing: any[];
  currentPeople: any[];
  deletedIds: Set<string>;
  restoredIds: Set<string>;
  issues: Issue[];
}

// No new-side record means their fields read old → empty.
function newRecordFor(type: string, person: any): DiffRecord {
  return type === DiffType.REMOVED ? null : person;
}

function statusFor(
  type: string,
  personId: string,
  deletedIds: Set<string>,
  restoredIds: Set<string>,
): RailStatusKey {
  // Before the diff verdict: restoring copies the old record back, so they compare
  // identical and would otherwise read `unchanged`.
  if (restoredIds.has(personId)) return RailStatus.RESTORED;
  // foldDeletions already re-typed them REMOVED; only the set says who caused it.
  if (deletedIds.has(personId)) return RailStatus.DELETED;
  return type as RailStatusKey;
}

export function buildReviewCards({
  existing,
  currentPeople,
  deletedIds,
  restoredIds,
  issues,
}: BuildCardsInput): ReviewCard[] {
  const olds = Array.isArray(existing) ? existing : [];
  const news = Array.isArray(currentPeople) ? currentPeople : [];
  const issuesByPersonId = indexIssuesByPersonId(issues);

  const { diffEntries, unchangedEntries } = foldDeletions(
    computePeopleDiff(olds, news, recordsDiffer),
    deletedIds,
  );

  // Slot order, so editing never re-sorts the list. People the scrape dropped
  // have no slot and trail at the end.
  const slot = new Map(news.map((p, i) => [p?.id, i]));
  const ordered = [...diffEntries, ...unchangedEntries].sort((a, b) => {
    const ai = slot.get(a.person?.id);
    const bi = slot.get(b.person?.id);
    if (ai === undefined) return bi === undefined ? 0 : 1;
    if (bi === undefined) return -1;
    return ai - bi;
  });

  return ordered.map((entry) => {
    const personId = entry.person?.id;
    const cardIssues = issuesByPersonId.get(personId) ?? [];
    const newRecord = newRecordFor(entry.type, entry.person);
    return {
      personId,
      status: statusFor(entry.type, personId, deletedIds, restoredIds),
      oldRecord: entry.from,
      newRecord,
      surviving: survivingFields(entry.from, newRecord, cardIssues),
      issues: cardIssues,
    };
  });
}

// Reported separately because there is no card to attach it to — that is the
// problem: one of the two people has no diff entry at all.
export function duplicateIdsFor({
  existing,
  currentPeople,
}: Pick<BuildCardsInput, "existing" | "currentPeople">): string[] {
  return (
    computePeopleDiff(
      Array.isArray(existing) ? existing : [],
      Array.isArray(currentPeople) ? currentPeople : [],
      recordsDiffer,
    ).duplicateIds ?? []
  );
}

// The shape useFrozenFields folds.
export function cardFields(cards: ReviewCard[]) {
  return cards.map(({ personId, surviving }) => ({ personId, surviving }));
}

// ── Grouping and order (§3) ──────────────────────────────────────────────────

// One constant so every consumer orders the same way.
export const STATUS_ORDER: RailStatusKey[] = [
  RailStatus.CHANGED,
  RailStatus.ADDED,
  RailStatus.UNCHANGED,
  RailStatus.REMOVED,
  RailStatus.RESTORED,
  RailStatus.DELETED,
];

// Deletion counts deliberately: otherwise someone marked for removal with nothing
// else changed would hide in the faded group.
export function needsReview(card: ReviewCard): boolean {
  return (
    // Context fields are always visible, so counting them would put everyone in
    // To review. See isContextField.
    card.surviving.some((field) => !isContextField(field.field)) ||
    card.issues.length > 0 ||
    card.status === RailStatus.DELETED
  );
}

export interface GroupedCards {
  toReview: ReviewCard[];
  unchanged: ReviewCard[];
}

// Ordered by status, then issues first within each bucket. Sorting is stable in
// JS, so cards with equal keys keep the slot order buildReviewCards gave them.
export function groupCards(cards: ReviewCard[]): GroupedCards {
  const rank = (card: ReviewCard) => {
    const status = STATUS_ORDER.indexOf(card.status);
    return status === -1 ? STATUS_ORDER.length : status;
  };
  const ordered = [...cards].sort((a, b) => {
    if (rank(a) !== rank(b)) return rank(a) - rank(b);
    return Number(b.issues.length > 0) - Number(a.issues.length > 0);
  });
  return {
    toReview: ordered.filter(needsReview),
    unchanged: ordered.filter((card) => !needsReview(card)),
  };
}

// ── The publish set, and what blocks it (§7, §9) ─────────────────────────────

// What publishing sends. Mirrors buildPeoplePatch's filter, which is the contract.
export function publishSet(cards: ReviewCard[]): ReviewCard[] {
  return cards.filter(
    (card) => card.newRecord != null && card.status !== RailStatus.DELETED,
  );
}

export interface BlockingError {
  personId: string;
  name: string;
  fieldLabel: string;
  message: string;
}

// Scans the schema, not the screen: a collapsed field can still block publishing.
// Publish set only — an empty required field on someone being dropped is moot.
export function blockingErrors(cards: ReviewCard[]): BlockingError[] {
  const errors: BlockingError[] = [];
  for (const card of publishSet(cards)) {
    for (const field of FIELD_SCHEMA) {
      const message = fieldError(field, card.newRecord);
      if (!message) continue;
      errors.push({
        personId: card.personId,
        name: card.newRecord?.name || "(unnamed)",
        fieldLabel: field.label,
        message,
      });
    }
  }
  return errors;
}

// Seat order, at-large first — how a published roster reads.
export function bySeat(cards: ReviewCard[], jurisdictionOcdid: string | null | undefined) {
  const seat = (card: ReviewCard) => {
    const division = parseDivision(card.newRecord?.office?.division_ocdid, jurisdictionOcdid);
    if (division.type === DIVISION_AT_LARGE) return -1;
    const value = Number.parseInt(division.value, 10);
    return Number.isNaN(value) ? Number.MAX_SAFE_INTEGER : value;
  };
  return [...cards].sort((a, b) => seat(a) - seat(b));
}

// ── Reviewer deletions, folded into the diff ─────────────────────────────────

export interface DiffEntry {
  type: string;
  person: any;
  from: any;
}

export interface PeopleDiffResult {
  diffEntries: DiffEntry[];
  unchangedEntries: DiffEntry[];
  // Ids that appeared twice in a list. Carried through rather than dropped, so
  // the card can say a person is missing from the diff (§21.8).
  duplicateIds?: string[];
}

// computePeopleDiff knows nothing about reviewer deletions, so an untouched
// deleted person comes back UNCHANGED. This folds the decision in afterwards.
// Deleting someone the scrape *added* is a net no-op and drops out entirely.
export function foldDeletions(
  { diffEntries, unchangedEntries, duplicateIds }: PeopleDiffResult,
  deletedIds: Set<string>,
): PeopleDiffResult {
  if (deletedIds.size === 0) return { diffEntries, unchangedEntries, duplicateIds };

  const kept: DiffEntry[] = [];
  const survives = (entry: DiffEntry) =>
    !(deletedIds.has(entry.person?.id) && entry.type === DiffType.ADDED);

  for (const entry of diffEntries) {
    if (!survives(entry)) continue;
    kept.push(
      deletedIds.has(entry.person?.id)
        ? { ...entry, type: DiffType.REMOVED }
        : entry,
    );
  }

  const stillUnchanged: DiffEntry[] = [];
  for (const entry of unchangedEntries) {
    if (!deletedIds.has(entry.person?.id)) {
      stillUnchanged.push(entry);
      continue;
    }
    // An unchanged person the reviewer dropped is a change to the list, so it
    // moves out of the unchanged bucket entirely.
    kept.push({ ...entry, type: DiffType.REMOVED });
  }

  return { diffEntries: kept, unchangedEntries: stillUnchanged, duplicateIds };
}

// ── Linking an added person to an existing record ────────────────────────────

// An `added` row is actually an existing record: it adopts that id so publish
// overlays rather than duplicates, and the old name folds into other_names so the
// next scrape resolves by alias.
export function buildLinkUpdates(
  added: any,
  target: any,
): { id: string; other_names: string[] } {
  // Deduped, minus blanks and the added person's own name.
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

// Declared in field-model.ts (the collapse rule reads it); re-exported here so
// consumers have one import site.
export { type Issue } from "./field-model.js";

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
