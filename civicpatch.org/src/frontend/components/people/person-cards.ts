import { computePeopleDiff, DiffType } from "../../utils/diff-utils.js";
import {
  divisionOf,
  heldMembershipLabel,
  type HeldMembership,
  postLabelFor,
  postName,
  postsHeld,
  type Post,
} from "../posts-list/posts-model.js";
import {
  FIELD_SCHEMA,
  fieldError,
  getFieldValue,
  isContextField,
  POST_FIELD,
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

// "removed" and "deleted" are synonyms in English but mean different things here.
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

// The post's own label alone, no membership label — for a diff that should only ever compare
// whether the post itself changed, not two independently-changing pieces of text at once (see
// diff-card.ts's own comment on `renderPostFieldValue`).
export function postNameFor(card: PersonCard, posts: Post[] = []): string {
  const record = personOf(card);
  const pickedPostId = record ? getFieldValue(record, POST_FIELD) : null;
  const pickedLabel = pickedPostId ? postLabelFor(pickedPostId, posts) : "";
  if (pickedLabel) return pickedLabel;

  const source = personOf(card)?.memberships ?? [];
  if (source.length) return source.map(postName).join("; ");
  return record?.labels?.join("; ") ?? "";
}

// What the occupant's own labels said beyond the post's own name — rendered plainly, on its
// own line, never diffed against anything.
export function membershipLabelFor(card: PersonCard): string {
  const record = personOf(card);
  // A reviewer's own explicit pick names a post, not a label — the label input beside the
  // picker is a separate, later action (office-edits.ts), so there is nothing to show yet.
  if (record && getFieldValue(record, POST_FIELD)) return "";
  return (personOf(card)?.memberships ?? [])
    .map((entry) => entry.label || "")
    .filter(Boolean)
    .join("; ");
}

// The two above, combined into one line — for the two remaining spots too tight for a
// two-line card (review-modal.ts's person switcher, the folded review chip).
export function postsFor(card: PersonCard, posts: Post[] = []): string {
  const record = personOf(card);
  const pickedPostId = record ? getFieldValue(record, POST_FIELD) : null;
  const pickedLabel = pickedPostId ? postLabelFor(pickedPostId, posts) : "";
  if (pickedLabel) return pickedLabel;

  const source = personOf(card)?.memberships ?? [];
  if (source.length) return postsHeld(source);
  return record?.labels?.join("; ") ?? "";
}

export const personOf = (card: PersonCard) => card.newRecord ?? card.oldRecord;

export interface CardsResult {
  cards: PersonCard[];
  duplicateIds: string[];
}

export interface PersonCard {
  personId: string;
  organizationId?: string;
  status: PersonStatusKey;
  oldRecord: DiffRecord;
  newRecord: DiffRecord;
  surviving: SurvivingField[];
  issues: Issue[];
}

export function cardKey(card: {
  personId: string;
  organizationId?: string;
}): string {
  return card.organizationId
    ? `${card.personId}:${card.organizationId}`
    : card.personId;
}

/** Whom a card key is about. A review card is one person, so its key is their id; a roster row
 * is a person in one body, so one person may have several keys. */
export function personIdIn(key: string): string {
  return key.split(":")[0];
}

/** Which body a card key names, or null for a key that names the person whole — which is what
 * a review card's key is, and what Reset hands back. */
export function organizationIn(key: string): string | null {
  return key.split(":")[1] ?? null;
}

export interface BuildCardsInput {
  existing: any[];
  currentPeople: any[];
  removedIds: Set<string>;
  restoredIds: Set<string>;
  issues: Issue[];
}

const postIdsIn = (memberships: HeldMembership[] | undefined): string =>
  [...new Set((memberships ?? []).map((membership) => membership.post_id))]
    .sort()
    .join("|");

/** Whether this scrape changed which posts somebody holds. Both sides are the same fold, so a
 * body this scrape never read derives identically on each and cannot read as a move. */
function postMoved(
  before: HeldMembership[] | undefined,
  after: HeldMembership[] | undefined,
): boolean {
  return !!after?.length && postIdsIn(before) !== postIdsIn(after);
}

// `survivingFields` cannot see the office on its own — `post_id` is never a raw scraped value
// (nothing writes it onto a record until a reviewer picks one), so there is nothing for a field
// diff to compare. A move or a first appearance is the post set changing; the case that misses
// is the post staying put while this scrape recomposed the membership label.
function officeSurvivingField(
  before: HeldMembership[] | undefined,
  after: HeldMembership[] | undefined,
): SurvivingField | null {
  if (!after?.length) return null;
  const moved = postMoved(before, after);
  // Per body, as the office itself is: a person on two bodies has a label in each.
  const labelChanged = after.some(
    (membership) =>
      (membership.label ?? null) !==
      (heldMembershipLabel(before, membership.organization_id ?? null) ?? null),
  );
  if (!moved && !labelChanged) return null;
  return {
    field: FIELD_SCHEMA.find((field) => field.key === POST_FIELD)!,
    // Matches every other field's own state on the same card: "added" for a first
    // appearance, "changed" for a move or a recomposed label on a seat that stayed put.
    state: before?.length ? "changed" : "added",
    reason: "diff",
    error: null,
  };
}

export interface MovedNote {
  from: string;
  to: string;
}

// postMoved already folds a seat change into one CHANGED card; this says which
// post it left and which it landed in.
export function movedNote(card: PersonCard, posts: Post[]): MovedNote | null {
  const oldMemberships = card.oldRecord?.memberships;
  if (!postMoved(oldMemberships, card.newRecord?.memberships)) return null;
  const from = oldMemberships?.length
    ? oldMemberships.map(postName).join("; ")
    : (card.oldRecord?.labels?.join("; ") ?? "");
  const to = postNameFor(card, posts);
  return from && from !== to ? { from, to } : null;
}

function statusFor(
  type: string,
  personId: string,
  removedIds: Set<string>,
  restoredIds: Set<string>,
): PersonStatusKey {
  // Restoring copies the old record back, so it would otherwise diff as `unchanged`.
  if (restoredIds.has(personId)) return PersonStatus.RESTORED;
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
    const moved = postMoved(entry.from?.memberships, entry.person?.memberships);
    let status = statusFor(entry.type, personId, removedIds, restoredIds);
    // A move is a change even when every field matches.
    if (status === PersonStatus.UNCHANGED && moved) {
      status = PersonStatus.CHANGED;
    }
    // Only the scrape dropping someone leaves no new-side record.
    const newRecord = status === PersonStatus.REMOVED ? null : entry.person;
    // Departing is one decision, so it carries no field list: against a null new side every
    // field they had reads "cleared", and nine cleared fields would say nine things to review
    // about a card that asks one question.
    const surviving = DEPARTING.has(status)
      ? []
      : survivingFields(entry.from, newRecord, cardIssues);
    const office = officeSurvivingField(
      entry.from?.memberships,
      newRecord?.memberships,
    );
    return {
      personId,
      status,
      oldRecord: entry.from,
      newRecord,
      surviving:
        office && !surviving.some((field) => field.field.key === POST_FIELD)
          ? [...surviving, office]
          : surviving,
      issues: cardIssues,
    };
  });
}

// Reported separately: there is no card to attach it to — one of the pair has no diff entry.
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

export function needsReview(card: PersonCard): boolean {
  return (
    // Context fields are always visible, so they only count here on error.
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

// Scans the schema, not the screen: a collapsed field can still block publishing.
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

// computePeopleDiff knows nothing about reviewer removals, so an untouched one reads UNCHANGED.
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

export function adjacentPeer(
  cards: PersonCard[],
  currentId: string,
  direction: -1 | 1,
): PersonCard | undefined {
  const index = cards.findIndex((c) => c.personId === currentId);
  return index === -1 ? undefined : cards[index + direction];
}

// Whether a modal open on `personId` should show a prev/next affordance — shared by every
// caller that opens one PersonCard at a time out of a list (review session, roster editor).
export function navHintFor(
  peers: PersonCard[],
  personId: string,
): { hasPrev: boolean; hasNext: boolean } | undefined {
  if (peers.length <= 1) return undefined;
  const index = peers.findIndex((c) => c.personId === personId);
  return { hasPrev: index > 0, hasNext: index < peers.length - 1 };
}
