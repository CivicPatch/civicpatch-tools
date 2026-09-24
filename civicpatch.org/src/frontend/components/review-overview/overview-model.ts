import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import {
  DEPARTING,
  personOf,
  PersonStatus,
  type PersonCard,
} from "../people/person-cards.js";
import { UNMATCHED_ROLE_ID } from "../../schemas/role-types.js";
import { type HeldMembership } from "../posts-list/posts-model.js";
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


/** One person as one organization sees them: the card, and the office they hold there. A person
 * holding posts in two organizations is two of these, which puts them in both sections. */
export interface CardInOrganization {
  card: PersonCard;
  /** What this scrape would leave them holding here — or, when it leaves them out of this
   * body, the office they are losing, so the row can still name what is going. */
  office: PostRole;
  leaving: boolean;
}

interface MembershipRow extends HeldMembership {
  role_label: string;
}

const asOffice = (membership: MembershipRow): PostRole => ({
  role_id: membership.role_id,
  role_label: membership.role_label,
  post_label: membership.post_label,
  membership_label: membership.label,
});

export interface OrganizationSection {
  organizationId: string;
  ranked: RoleGroup<CardInOrganization>[];
  unmatched: CardInOrganization[];
}

export interface ReviewOrganizationSections {
  organizations: OrganizationSection[];
  /** People leaving: the scrape did not find them, or a reviewer took them off. */
  departing: PersonCard[];
  /** Nobody has given them an office yet — somebody a reviewer just added. They used to be
   * filed with the departing, which read as "not found" about a person who had just arrived. */
  unplaced: PersonCard[];
}

/** Nothing was found in this organization: everyone listed here is leaving it. Publishing
 * changes nothing here, whether the scrape read no page for it or read one and returned nobody,
 * because closing skips an organization with nobody in it. */
export function foundNobody(entries: CardInOrganization[]): boolean {
  return entries.length > 0 && entries.every((entry) => entry.leaving);
}

/** What a row proposes in its own body, or what it is losing — which is what the section shows
 * either way. `leaving` is the second: nothing proposed here any more. */
function officeOf(card: PersonCard): { office: PostRole; leaving: boolean } | null {
  const inHere = (membership: MembershipRow) =>
    membership.organization_id === card.organizationId;
  const proposed = (card.newRecord?.memberships ?? []).filter(inHere);
  const held = (card.oldRecord?.memberships ?? []).filter(inHere);
  const office = proposed[0] ?? held[0];
  return office ? { office: asOffice(office), leaving: !proposed.length } : null;
}

/** The same grouping one level down: a section per organization, roles inside it. A person is
 * listed in each organization they hold a post in on either side, carrying that organization's
 * own office, so the council section shows their council post and the mayor's office the
 * mayoralty. Both sides, so a body this scrape emptied still has a section saying so.
 *
 * Until 2026-09-23 the sections came from `ProposedChange`, which is why a proposed post could
 * be named before the post existed; the fold names it from `PostKey` and the rows carry it.
 */
export function sectionsByOrganization(
  cards: PersonCard[],
  roleOrder: string[],
  organizationOrder: string[] = [],
): ReviewOrganizationSections {
  const departing = cards.filter((card) => DEPARTING.has(card.status));
  const staying = cards.filter((card) => !DEPARTING.has(card.status));

  const byOrganization = new Map<string, CardInOrganization[]>();
  const unplaced: PersonCard[] = [];
  for (const card of staying) {
    const here = card.organizationId ? officeOf(card) : null;
    if (!card.organizationId || !here) {
      unplaced.push(card);
      continue;
    }
    const listed = byOrganization.get(card.organizationId) ?? [];
    listed.push({ card, ...here });
    byOrganization.set(card.organizationId, listed);
  }

  const rank = (organizationId: string) => {
    const index = organizationOrder.indexOf(organizationId);
    return index === -1 ? organizationOrder.length : index;
  };
  const organizations = [...byOrganization]
    .sort(([a], [b]) => rank(a) - rank(b))
    .map(([organizationId, listed]) => {
      const isUnmatched = (entry: CardInOrganization) =>
        entry.office.role_id === UNMATCHED_ROLE_ID;
      const ranked = groupByRole(
        listed
          .filter((entry) => !isUnmatched(entry))
          .map((entry) => ({
            id: entry.card.personId,
            memberships: [entry.office],
            entry,
          })),
        roleOrder,
      ).map((group) => ({ ...group, people: group.people.map(({ entry }) => entry) }));
      return { organizationId, ranked, unmatched: listed.filter(isUnmatched) };
    });

  return { organizations, departing, unplaced };
}
