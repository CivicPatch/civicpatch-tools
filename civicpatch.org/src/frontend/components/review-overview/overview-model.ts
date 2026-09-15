import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import {
  DEPARTING,
  personOf,
  PersonStatus,
  soleProposalFor,
  type PersonCard,
  type ProposedChange,
} from "../people/person-cards.js";
import { UNMATCHED_ROLE_ID } from "../../utils/role-types.js";
import { isContextField, type SurvivingField } from "../fields/field-model.js";
import {
  groupByRole,
  type RoleGroup,
  type PostRole,
} from "../people/person-card-grid-model.js";

const FIELD_ORDER = [
  "labels",
  "emails",
  "phones",
  "urls",
  "name",
  "other_names",
  "start_date",
  "end_date",
  "image",
];

const REASON_RANK: Record<string, number> = {
  error: 0,
  issue: 1,
  diff: 2,
  context: 3,
};

export const STATUS_BADGE: Partial<Record<string, string>> = {
  [PersonStatus.CHANGED]: "Changed",
  [PersonStatus.ADDED]: "New",
  [PersonStatus.REMOVED]: "Not in scrape",
  [PersonStatus.DELETED]: "Removed",
  [PersonStatus.RESTORED]: "Restored",
};

export const ATTENTION_COPY = {
  error: { icon: "triangle-exclamation", label: "Blocks publishing" },
};

function fieldRank(key: string): number {
  const i = FIELD_ORDER.indexOf(key);
  return i === -1 ? FIELD_ORDER.length : i;
}

export function byRank(a: SurvivingField, b: SurvivingField): number {
  const reason = (REASON_RANK[a.reason] ?? 9) - (REASON_RANK[b.reason] ?? 9);
  return reason || fieldRank(a.field.key) - fieldRank(b.field.key);
}

export function attentionOf(card: PersonCard): "error" | null {
  return card.surviving.some((field) => field.error) ? "error" : null;
}

// Mirrors shared.schemas.IssueCode: these describe exactly what the status badge (or the
// "Moved" note on the post field) already says, so repeating them as an issue chip too
// would just say the same thing twice.
const REDUNDANT_ISSUE_CODES = new Set([
  "absent_person",
  "new_person",
  "moved_person",
  "changed_field",
]);

export function issueTypesOf(card: PersonCard): string[] {
  return card.issues
    .filter((issue) => !REDUNDANT_ISSUE_CODES.has(issue.code))
    .map((issue) => issue.code.replace(/_/g, " "));
}

export interface TallyEntry {
  status: string;
  label: string;
  count: number;
}

const TALLY_LABEL: Record<string, string> = {
  [PersonStatus.ADDED]: "added",
  [PersonStatus.CHANGED]: "changed",
  [PersonStatus.REMOVED]: "not in scrape",
  [PersonStatus.DELETED]: "removed",
  [PersonStatus.RESTORED]: "restored",
  [PersonStatus.UNCHANGED]: "unchanged",
};

const TALLY_ORDER = [
  PersonStatus.ADDED,
  PersonStatus.CHANGED,
  PersonStatus.REMOVED,
  PersonStatus.DELETED,
  PersonStatus.RESTORED,
  PersonStatus.UNCHANGED,
];

export function tallyOf(cards: PersonCard[]): TallyEntry[] {
  const counts = new Map<string, number>();
  for (const card of cards) {
    counts.set(card.status, (counts.get(card.status) ?? 0) + 1);
  }
  return TALLY_ORDER.filter((status) => counts.get(status)).map((status) => ({
    status,
    label: TALLY_LABEL[status],
    count: counts.get(status) as number,
  }));
}

export function visibleFields(card: PersonCard): SurvivingField[] {
  return card.surviving
    .filter((field) => !isContextField(field.field))
    .sort(byRank);
}

export type SourceMap = Map<string, { number: number; colorClass: string }>;

export function sourceMapFor(cards: PersonCard[]): SourceMap {
  const seen: { url: string }[] = [];
  const known = new Set<string>();
  for (const card of cards) {
    for (const url of card.newRecord?.source_urls ?? []) {
      if (url && !known.has(url)) {
        known.add(url);
        seen.push({ url });
      }
    }
  }
  return buildSourceUrlMap(seen);
}

export interface Run {
  folded: boolean;
  cards: PersonCard[];
}

export function runsOf(cards: PersonCard[]): Run[] {
  return cards.reduce<Run[]>((runs, card) => {
    const folded = card.status === PersonStatus.UNCHANGED;
    const last = runs[runs.length - 1];
    if (folded && last?.folded) last.cards.push(card);
    else runs.push({ folded, cards: [card] });
    return runs;
  }, []);
}

export interface ReviewSections {
  ranked: RoleGroup<PersonCard>[];
  unmatched: PersonCard[];
  departing: PersonCard[];
}

function roleMembershipsFor(
  proposal: ProposedChange | null,
  card: PersonCard,
): PostRole[] | undefined {
  if (!proposal) return personOf(card)?.memberships;
  return [{ role_id: proposal.role_id, role_label: proposal.role_label }];
}

/** Cards grouped for display the way the jurisdiction grid groups people — by role, ranked
 * groups first — plus the trailing bucket a review needs that a published roster doesn't: a
 * seat the scrape couldn't name a role for at all. */
export function sectionsOf(
  cards: PersonCard[],
  proposals: Map<string, ProposedChange[]>,
  roleOrder: string[],
): ReviewSections {
  const departing = cards.filter((card) => DEPARTING.has(card.status));
  // Each staying card's sole proposal, resolved once rather than re-derived by every filter
  // and the group-membership step below.
  const staying = cards
    .filter((card) => !DEPARTING.has(card.status))
    .map((card) => ({
      card,
      proposal: soleProposalFor(card.personId, proposals),
    }));
  const isUnmatched = (proposal: ProposedChange | null) =>
    proposal?.role_id === UNMATCHED_ROLE_ID;
  const unmatched = staying
    .filter(({ proposal }) => isUnmatched(proposal))
    .map(({ card }) => card);
  const groupable = staying.filter(({ proposal }) => !isUnmatched(proposal));
  const groups = groupByRole(
    groupable.map(({ card, proposal }) => ({
      id: card.personId,
      memberships: roleMembershipsFor(proposal, card),
      card,
    })),
    roleOrder,
  ).map((group) => ({
    ...group,
    people: group.people.map(({ card }) => card),
  }));
  return { ranked: groups, unmatched, departing };
}
