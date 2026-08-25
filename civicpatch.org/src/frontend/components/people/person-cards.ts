// One card per person: what happened to them, and which fields survive the collapse rule.

import { computePeopleDiff, DiffType } from "../../utils/diff-utils.js";
import { divisionOf, postsHeld } from "../posts-list/posts-model.js";
import {
  FIELD_SCHEMA,
  fieldError,
  isContextField,
  recordsDiffer,
  survivingFields,
  type DiffRecord,
  type Issue,
  type SurvivingField,
} from "../fields/field-model.js";
import {
  parseDivision,
  DIVISION_AT_LARGE,
} from "../edit-people/person-edit-utils.js";

// `deleted` and `restored` are reviewer decisions, not diff verdicts — hence not DiffType values.
export const PersonStatus = Object.freeze({
  CHANGED: "changed",
  ADDED: "added",
  UNCHANGED: "unchanged",
  REMOVED: "removed",
  DELETED: "deleted",
  RESTORED: "restored",
});

export type PersonStatusKey = (typeof PersonStatus)[keyof typeof PersonStatus];

// Each label names its actor: "removed" and "deleted" are synonyms in English but mean
// different things here, so neither bare word is ever UI copy.
export const STATUS_LABEL: Record<PersonStatusKey, string> = {
  [PersonStatus.CHANGED]: "changed",
  [PersonStatus.ADDED]: "new",
  [PersonStatus.UNCHANGED]: "unchanged",
  [PersonStatus.REMOVED]: "not found in scrape",
  [PersonStatus.DELETED]: "you removed",
  [PersonStatus.RESTORED]: "restored",
};

// Both routes out of the roster. They render identically — who caused it is in the banner.
export const DEPARTING = new Set<string>([
  PersonStatus.REMOVED,
  PersonStatus.DELETED,
]);

export function postsFor(
  card: PersonCard,
  proposedByPersonId?: Map<string, ProposedChange[]>,
): string {
  const proposed = proposedByPersonId?.get(card.personId) ?? [];
  if (proposed.length) {
    // From the derivation rather than from memberships: the person holds none yet.
    return postsHeld(
      proposed.map((change) => ({
        post_label: change.post_label,
        label: change.label,
      })),
    );
  }
  const record = personOf(card);
  if (record?.memberships?.length) return postsHeld(record.memberships);
  return record?.office?.name ?? "";
}

/** A list per person, not one change: a person can be proposed onto more than one post, and
 * keying a plain Map on `person_id` kept only the last of them. */
export function proposalsByPersonId(
  changes: ProposedChange[],
): Map<string, ProposedChange[]> {
  const byPerson = new Map<string, ProposedChange[]>();
  for (const change of changes) {
    byPerson.set(change.person_id, [
      ...(byPerson.get(change.person_id) ?? []),
      change,
    ]);
  }
  return byPerson;
}

// The new side is live; someone the scrape didn't find has only the old side.
export const personOf = (card: PersonCard) => card.newRecord ?? card.oldRecord;

export interface CardsResult {
  cards: PersonCard[];
  duplicateIds: string[];
}

// The card's only source for "which post would this person land in" — they hold no
// membership yet.
export interface ProposedChange {
  person_id: string;
  disposition: string;
  role_id: string;
  role_label: string;
  division_ocdid: string;
  label: string | null;
  // Rendered by `core.membership_label`, because a proposed post may not exist yet.
  post_label: string;
}

export interface PersonCard {
  personId: string;
  status: PersonStatusKey;
  oldRecord: DiffRecord;
  newRecord: DiffRecord;
  surviving: SurvivingField[];
  issues: Issue[];
}

export interface BuildCardsInput {
  existing: any[];
  currentPeople: any[];
  removedIds: Set<string>;
  restoredIds: Set<string>;
  issues: Issue[];
}

function statusFor(
  type: string,
  personId: string,
  removedIds: Set<string>,
  restoredIds: Set<string>,
): PersonStatusKey {
  // Before the diff verdict: restoring copies the old record back, so they compare identical
  // and would otherwise read `unchanged`.
  if (restoredIds.has(personId)) return PersonStatus.RESTORED;
  // foldRemovals already re-typed them REMOVED; only the set says who caused it.
  if (removedIds.has(personId)) return PersonStatus.DELETED;
  return type as PersonStatusKey;
}

export function buildPersonCards({
  existing,
  currentPeople,
  removedIds,
  restoredIds,
  issues,
}: BuildCardsInput): PersonCard[] {
  const olds = Array.isArray(existing) ? existing : [];
  const news = Array.isArray(currentPeople) ? currentPeople : [];
  const issuesByPersonId = indexIssuesByPersonId(issues);

  const { diffEntries, unchangedEntries } = foldRemovals(
    computePeopleDiff(olds, news, recordsDiffer),
    removedIds,
  );

  // Slot order, so editing never re-sorts the list. People the scrape dropped trail at the end.
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
    const status = statusFor(entry.type, personId, removedIds, restoredIds);
    // Only the scrape dropping someone leaves no new-side record; a reviewer removal is a
    // decision about a row that is still in the list.
    const newRecord = status === PersonStatus.REMOVED ? null : entry.person;
    return {
      personId,
      status,
      oldRecord: entry.from,
      newRecord,
      surviving: survivingFields(entry.from, newRecord, cardIssues),
      issues: cardIssues,
    };
  });
}

// Reported separately because there is no card to attach it to — that is the problem: one of
// the two people has no diff entry at all.
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
export function cardFields(cards: PersonCard[]) {
  return cards.map(({ personId, surviving }) => ({ personId, surviving }));
}

// ── What needs a decision (§3) ───────────────────────────────────────────────

// Deletion counts deliberately: someone marked for removal with nothing else changed would
// otherwise hide in the faded group.
export function needsReview(card: PersonCard): boolean {
  return (
    // Context fields are always visible, so counting them would put everyone in To review —
    // unless one carries an error, which blocks publish and cannot fold away unseen.
    card.surviving.some(
      (field) => !isContextField(field.field) || field.error,
    ) ||
    card.issues.length > 0 ||
    card.status === PersonStatus.DELETED
  );
}

// ── The publish set, and what blocks it (§7, §9) ─────────────────────────────

// Mirrors buildPeoplePatch's filter, which is the contract.
export function publishSet(cards: PersonCard[]): PersonCard[] {
  return cards.filter(
    (card) => card.newRecord != null && card.status !== PersonStatus.DELETED,
  );
}

export interface BlockingError {
  personId: string;
  name: string;
  fieldLabel: string;
  message: string;
}

// Scans the schema, not the screen: a collapsed field can still block publishing. Publish set
// only — an empty required field on someone being dropped is moot.
export function blockingErrors(cards: PersonCard[]): BlockingError[] {
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

// At-large first, which is how a published roster reads.
export function byDivision(
  cards: PersonCard[],
  jurisdictionOcdid: string | null | undefined,
) {
  const division = (card: PersonCard) => {
    const division = parseDivision(
      divisionOf(card.newRecord?.memberships ?? []),
      jurisdictionOcdid,
    );
    if (division.type === DIVISION_AT_LARGE) return -1;
    const value = Number.parseInt(division.value, 10);
    return Number.isNaN(value) ? Number.MAX_SAFE_INTEGER : value;
  };
  return [...cards].sort((a, b) => division(a) - division(b));
}

// ── Reviewer removals, folded into the diff ──────────────────────────────────

export interface DiffEntry {
  type: string;
  person: any;
  from: any;
}

export interface PeopleDiffResult {
  diffEntries: DiffEntry[];
  unchangedEntries: DiffEntry[];
  // Carried through rather than dropped, so the card can say a person is missing (§21.8).
  duplicateIds?: string[];
}

// computePeopleDiff knows nothing about reviewer removals, so an untouched removed person
// comes back UNCHANGED. Every removed person keeps a card, including one the scrape added.
export function foldRemovals(
  { diffEntries, unchangedEntries, duplicateIds }: PeopleDiffResult,
  removedIds: Set<string>,
): PeopleDiffResult {
  if (removedIds.size === 0)
    return { diffEntries, unchangedEntries, duplicateIds };

  const isRemoved = (entry: DiffEntry) => removedIds.has(entry.person?.id);
  const kept: DiffEntry[] = [];
  const stillUnchanged: DiffEntry[] = [];

  for (const entry of diffEntries) {
    kept.push(isRemoved(entry) ? { ...entry, type: DiffType.REMOVED } : entry);
  }

  // An unchanged person the reviewer dropped is a change to the list, so they leave the bucket.
  for (const entry of unchangedEntries) {
    if (isRemoved(entry)) kept.push({ ...entry, type: DiffType.REMOVED });
    else stillUnchanged.push(entry);
  }

  return { diffEntries: kept, unchangedEntries: stillUnchanged, duplicateIds };
}

// ── Reviewer issues → per-card anchoring ─────────────────────────────────────

// Declared in field-model.ts; re-exported so consumers have one import site.
export { type Issue } from "../fields/field-model.js";

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
