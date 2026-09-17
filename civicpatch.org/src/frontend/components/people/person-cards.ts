import { computePeopleDiff, DiffType } from "../../utils/diff-utils.js";
import {
  divisionOf,
  heldMembershipLabel,
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
import { MEMBERSHIP_DISPOSITION, type ProposedChange } from "../../schemas/membership-proposal.js";

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

// The proposal or membership this card's post field currently resolves to — a proposal is the
// newer claim, so it outranks a held membership. Shared by the three functions below, each of
// which formats it differently; a reviewer's own explicit pick has no such source (it names an
// id, not a label pair), which is why each checks for one before ever calling this.
function heldSourceFor(
  card: PersonCard,
  proposedByPersonId?: Map<string, ProposedChange[]>,
): { post_label: string; label: string | null }[] {
  const proposed = proposedByPersonId?.get(card.personId) ?? [];
  if (proposed.length) {
    return proposed.map((change) => ({
      post_label: change.post.label,
      label: change.membership_label,
    }));
  }
  return personOf(card)?.memberships ?? [];
}

// The post's own label alone, no membership label — for a diff that should only ever compare
// whether the post itself changed, not two independently-changing pieces of text at once (see
// diff-card.ts's own comment on `renderPostFieldValue`).
export function postNameFor(
  card: PersonCard,
  proposedByPersonId?: Map<string, ProposedChange[]>,
  posts: Post[] = [],
): string {
  const record = personOf(card);
  const pickedPostId = record ? getFieldValue(record, POST_FIELD) : null;
  const pickedLabel = pickedPostId ? postLabelFor(pickedPostId, posts) : "";
  if (pickedLabel) return pickedLabel;

  const source = heldSourceFor(card, proposedByPersonId);
  if (source.length) return source.map(postName).join("; ");
  return record?.labels?.join("; ") ?? "";
}

// What the occupant's own labels said beyond the post's own name — rendered plainly, on its
// own line, never diffed against anything.
export function membershipLabelFor(
  card: PersonCard,
  proposedByPersonId?: Map<string, ProposedChange[]>,
): string {
  const record = personOf(card);
  // A reviewer's own explicit pick names a post, not a label — the label input beside the
  // picker is a separate, later action (office-changes.ts), so there is nothing to show yet.
  if (record && getFieldValue(record, POST_FIELD)) return "";
  return heldSourceFor(card, proposedByPersonId)
    .map((entry) => entry.label || "")
    .filter(Boolean)
    .join("; ");
}

// The two above, combined into one line — for the two remaining spots too tight for a
// two-line card (review-modal.ts's person switcher, the folded review chip).
export function postsFor(
  card: PersonCard,
  proposedByPersonId?: Map<string, ProposedChange[]>,
  posts: Post[] = [],
): string {
  const record = personOf(card);
  const pickedPostId = record ? getFieldValue(record, POST_FIELD) : null;
  const pickedLabel = pickedPostId ? postLabelFor(pickedPostId, posts) : "";
  if (pickedLabel) return pickedLabel;

  const source = heldSourceFor(card, proposedByPersonId);
  if (source.length) return postsHeld(source);
  return record?.labels?.join("; ") ?? "";
}

// A list per person: a person can be proposed onto more than one post.
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

export const personOf = (card: PersonCard) => card.newRecord ?? card.oldRecord;

export interface CardsResult {
  cards: PersonCard[];
  duplicateIds: string[];
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
  // Which post each person would land in — a field diff can't see a post move on its own.
  proposals?: Map<string, ProposedChange[]>;
}

// A card's one unambiguous proposed change, when it has exactly one — two or more is no
// single answer, so callers fall back to whatever they already hold. The same rule was
// being re-derived at three call sites (here, the office picker's default, and review's
// role grouping); this is the one place it is written.
export function soleProposalFor(
  personId: string,
  proposals: Map<string, ProposedChange[]> | undefined,
): ProposedChange | null {
  const proposed = proposals?.get(personId) ?? [];
  return proposed.length === 1 ? proposed[0] : null;
}

const postMoved = (
  personId: string,
  proposals?: Map<string, ProposedChange[]>,
): boolean =>
  (proposals?.get(personId) ?? []).some(
    (change) => change.disposition !== MEMBERSHIP_DISPOSITION.UNCHANGED,
  );

// `survivingFields` cannot see the office on its own — `post_id` is never a raw scraped
// value (nothing writes it onto a record until a reviewer picks one), so there is nothing
// for a field diff to compare. `postMoved` already covers a move or a first appearance via
// its disposition; this adds the one case the disposition alone misses: the post stayed put, but
// this scrape recomposed the membership label.
function officeSurvivingField(
  personId: string,
  proposals: Map<string, ProposedChange[]> | undefined,
  oldMemberships: { post_id: string; label: string | null }[] | undefined,
): SurvivingField | null {
  const change = soleProposalFor(personId, proposals);
  if (!change) return null;
  const labelChanged =
    (change.membership_label ?? null) !== (heldMembershipLabel(oldMemberships) ?? null);
  if (!postMoved(personId, proposals) && !labelChanged) return null;
  return {
    field: FIELD_SCHEMA.find((field) => field.key === POST_FIELD)!,
    // Matches every other field's own state on the same card: "added" for a first
    // appearance, "changed" for a move or a recomposed label on a seat that stayed put.
    state: change.disposition === MEMBERSHIP_DISPOSITION.NEW ? "added" : "changed",
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
export function movedNote(
  card: PersonCard,
  proposals: Map<string, ProposedChange[]> | undefined,
  posts: Post[],
): MovedNote | null {
  if (!postMoved(card.personId, proposals)) return null;
  const oldMemberships = card.oldRecord?.memberships;
  const from = oldMemberships?.length
    ? oldMemberships.map(postName).join("; ")
    : (card.oldRecord?.labels?.join("; ") ?? "");
  const to = postNameFor(card, proposals, posts);
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
  proposals,
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
    const moved = postMoved(personId, proposals);
    let status = statusFor(entry.type, personId, removedIds, restoredIds);
    // A move is a change even when every field matches.
    if (status === PersonStatus.UNCHANGED && moved) {
      status = PersonStatus.CHANGED;
    }
    // Only the scrape dropping someone leaves no new-side record.
    const newRecord = status === PersonStatus.REMOVED ? null : entry.person;
    const surviving = survivingFields(entry.from, newRecord, cardIssues);
    const office = officeSurvivingField(personId, proposals, entry.from?.memberships);
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
