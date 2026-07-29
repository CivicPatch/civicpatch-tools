// One card per person under review: what happened to them, and which of their
// fields survive the collapse rule. Pure, so both consumers read the same answer
// — the rail renders these, and useFrozenFields folds their surviving fields
// into the frozen set.

import { computePeopleDiff, DiffType } from "../../utils/diff-utils.js";
import {
  foldDeletions,
  indexIssuesByPersonId,
  recordsDiffer,
  survivingFields,
  type DiffRecord,
  type Issue,
  type SurvivingField,
} from "../people-diff/diff-model.js";

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
