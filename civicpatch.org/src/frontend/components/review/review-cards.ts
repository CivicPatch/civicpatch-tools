// One card per person under review: what happened to them, and which of their
// fields survive the collapse rule. Pure, so both consumers read the same answer
// — the rail renders these, and useFrozenFields folds their surviving fields
// into the frozen set.

import { computePeopleDiff, DiffType } from "../../utils/diff-utils.js";
import {
  FIELD_SCHEMA,
  fieldError,
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

// A card's status as the reviewer reads it. `deleted` and `restored` are
// reviewer decisions rather than diff verdicts, which is why they are not
// DiffType values. §11.3: each label names its actor, and the bare words
// "removed" and "deleted" never appear as UI copy — they are synonyms in English
// and mean different things here.
export const RailStatus = Object.freeze({
  CHANGED: "changed",
  ADDED: "added",
  UNCHANGED: "unchanged",
  REMOVED: "removed",
  DELETED: "deleted",
  RESTORED: "restored",
});

export type RailStatusKey = (typeof RailStatus)[keyof typeof RailStatus];

// How a status reads to the reviewer. Defined once, deliberately: §11.3 spends a
// page arguing that each label names its actor and that "removed" and "deleted"
// must never both appear as UI copy — an argument that has to stay true in one
// place, not three.
export const STATUS_LABEL: Record<RailStatusKey, string> = {
  [RailStatus.CHANGED]: "changed",
  [RailStatus.ADDED]: "new",
  [RailStatus.UNCHANGED]: "unchanged",
  [RailStatus.REMOVED]: "not found in scrape",
  [RailStatus.DELETED]: "you removed",
  [RailStatus.RESTORED]: "restored",
};

// Both routes out of the roster. They read identically to a reviewer — a red
// edge, a struck name, one Restore button — because someone scanning wants "who
// is leaving", and that answer is the same either way. Who caused it is in the
// banner text (§11.3).
export const DEPARTING = new Set<string>([RailStatus.REMOVED, RailStatus.DELETED]);

// The record a view should show for a card. The new side is the live one the
// reviewer edits; someone the scrape didn't find has only the old side.
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

// A person the scrape didn't find has no new-side record, so their fields read
// old → empty. Everyone else edits their new record.
function newRecordFor(type: string, person: any): DiffRecord {
  return type === DiffType.REMOVED ? null : person;
}

function statusFor(
  type: string,
  personId: string,
  deletedIds: Set<string>,
  restoredIds: Set<string>,
): RailStatusKey {
  // Checked before the diff verdict: restoring copies their old record into the
  // list, so they compare identical and would otherwise read as `unchanged` —
  // the exact reason restoredIds has to be remembered.
  if (restoredIds.has(personId)) return RailStatus.RESTORED;
  // foldDeletions has already re-typed a deleted person to REMOVED; only the
  // set says who caused it.
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

  // Slot order — each card keeps its place in currentPeople, so editing someone
  // never re-sorts the list under the reviewer. People the scrape dropped are
  // not in that list, so they trail at the end.
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

// Ids that appeared twice on either side. Reported separately from the cards
// because there is no card to attach it to — that is the whole problem: one of
// the two people has no entry in the diff at all (§21.8).
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

// The shape useFrozenFields folds. Split out so the page doesn't have to know
// how a card maps onto the freeze.
export function cardFields(cards: ReviewCard[]) {
  return cards.map(({ personId, surviving }) => ({ personId, surviving }));
}

// ── Grouping and order (§3) ──────────────────────────────────────────────────

// Held in one constant so Overview's two groups and any later ordering read the
// same sequence. `added` is what the old chips called "New" — one bucket, not two.
export const STATUS_ORDER: RailStatusKey[] = [
  RailStatus.CHANGED,
  RailStatus.ADDED,
  RailStatus.UNCHANGED,
  RailStatus.REMOVED,
  RailStatus.RESTORED,
  RailStatus.DELETED,
];

// A card needs review when it has surviving fields, a person-level issue, or the
// reviewer dropped it. Deletion is in the predicate deliberately: someone marked
// for removal with nothing else changed scores zero on the other two and would
// hide in the faded group — the one decision on the card would be the one thing
// not surfaced.
export function needsReview(card: ReviewCard): boolean {
  return (
    card.surviving.length > 0 ||
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

// Exactly what publishing sends: everyone with a record, minus those the
// reviewer dropped. Mirrors buildPeoplePatch's filter, which is the actual
// contract — a person the scrape didn't find has no new-side record and is
// therefore already absent.
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

// Every field of everyone being published — not only the fields on screen.
//
// The collapse rule can hide a field that still blocks publishing, which is
// exactly why freezing is one-directional (§2.1): scanning what is rendered
// would call a card publishable when it is not. It scans only the publish set,
// because a required field left empty on someone being dropped is irrelevant.
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

// Seat order, at-large first — the shape a published roster reads in, rather
// than the slot order the diff needs.
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

// computePeopleDiff compares two server-shaped lists and knows nothing about the
// reviewer marking someone for removal — so a deleted person whose fields are
// otherwise untouched comes back UNCHANGED and hides under that chip instead of
// appearing under Removed. This folds the decision in afterwards.
//
// It stays out of computePeopleDiff because deletion is a review-session state
// the other two consumers (diff-panel, data-panel) neither have nor want.
//
// Deleting someone the scrape *added* is a net no-op — they were never in the
// database and the patch omits them, so there is nothing to publish and nothing
// to show. Every other deletion becomes REMOVED. `person` deliberately stays the
// new-side record: renderRow reads its id to offer Undo.
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

// `Issue` itself lives in field-model.ts, because the collapse rule reads it and
// review-cards already imports from there — declaring it in both directions
// would be a cycle. Re-exported so consumers have one place to import from.
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
