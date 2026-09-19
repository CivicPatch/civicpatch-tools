import {
  CHANGESET_OPEN,
  type ReviewJurisdiction,
  type ChangeCounts,
  type RowError,
} from "./import-types.js";
import { jurisdictionOcdidToFriendly } from "../../components/ocdid-utils.js";
import { PersonStatus } from "../../components/people/person-cards.js";

export const REVIEW_FILTER = Object.freeze({
  ERRORS: "errors",
  HAS_ABSENT: "has-absent",
  HAS_ADDED: "has-added",
  HAS_CHANGED: "has-changed",
  UNCHANGED: "unchanged",
  OPEN: "open",
});
export type ReviewFilter = (typeof REVIEW_FILTER)[keyof typeof REVIEW_FILTER];

// One locality the batch touched: its card when the import made one, its errors when it hit any.
// A blocked or failed locality has errors and no card; a partial one has both.
export type Locality = {
  jurisdiction_ocdid: string;
  name: string;
  review: ReviewJurisdiction | null;
  errors: RowError[];
};

export function localities(
  jurisdictions: ReviewJurisdiction[],
  errors: RowError[],
): Locality[] {
  const errorsFor = (ocdid: string) =>
    errors.filter((error) => error.jurisdiction_ocdid === ocdid);
  const reviewed = new Set(jurisdictions.map((j) => j.jurisdiction_ocdid));
  const errorOnly = [...new Set(errors.map((error) => error.jurisdiction_ocdid))].filter(
    (ocdid) => !reviewed.has(ocdid),
  );
  return [
    ...jurisdictions.map((jurisdiction) => ({
      jurisdiction_ocdid: jurisdiction.jurisdiction_ocdid,
      name: jurisdiction.name,
      review: jurisdiction,
      errors: errorsFor(jurisdiction.jurisdiction_ocdid),
    })),
    ...errorOnly.map((ocdid) => ({
      jurisdiction_ocdid: ocdid,
      name: jurisdictionOcdidToFriendly(ocdid) || "No locality",
      review: null,
      errors: errorsFor(ocdid),
    })),
  ];
}

function isUnchanged(counts: ChangeCounts): boolean {
  return !counts.added_people && !counts.changed_people && !counts.absent_memberships;
}

// Lower is shown first: errors need fixing before anything else, then absences need the closest
// look, then new people, then edits.
function changeRank(locality: Locality): number {
  if (locality.errors.length) return 0;
  const counts = locality.review?.change_counts;
  if (!counts) return 4;
  if (counts.absent_memberships) return 1;
  if (counts.added_people) return 2;
  if (counts.changed_people) return 3;
  return 4;
}

export function byChangeRank(items: Locality[]): Locality[] {
  return [...items].sort(
    (a, b) => changeRank(a) - changeRank(b) || a.name.localeCompare(b.name),
  );
}

function matches(locality: Locality, filter: ReviewFilter): boolean {
  if (filter === REVIEW_FILTER.ERRORS) return locality.errors.length > 0;
  const review = locality.review;
  if (!review) return false;
  if (filter === REVIEW_FILTER.OPEN) return review.changeset_state === CHANGESET_OPEN;
  // Uncounted matches no change filter: it is not known to have changed, nor to be unchanged.
  const counts = review.change_counts;
  if (!counts) return false;
  if (filter === REVIEW_FILTER.HAS_ABSENT) return counts.absent_memberships > 0;
  if (filter === REVIEW_FILTER.HAS_ADDED) return counts.added_people > 0;
  if (filter === REVIEW_FILTER.HAS_CHANGED) return counts.changed_people > 0;
  return isUnchanged(counts);
}

// No filter shows everything.
export function filtered(items: Locality[], filter: ReviewFilter | null): Locality[] {
  if (filter === null) return items;
  return items.filter((locality) => matches(locality, filter));
}

// Counted over the whole batch, not what the other filters leave, so a count does not move
// when a neighbouring box is ticked.
export function filterCounts(items: Locality[]): Record<ReviewFilter, number> {
  return Object.fromEntries(
    Object.values(REVIEW_FILTER).map((filter) => [
      filter,
      items.filter((locality) => matches(locality, filter)).length,
    ]),
  ) as Record<ReviewFilter, number>;
}

export type ChangeBadge = { status: string; label: string };

// "2 added", "1 absent": only what is non-zero, coloured by the review tally's statuses. An
// absence is the tally's "not in scrape".
export function changeBadges(counts: ChangeCounts): ChangeBadge[] {
  const badges: ChangeBadge[] = [];
  if (counts.added_people)
    badges.push({ status: PersonStatus.ADDED, label: `${counts.added_people} added` });
  if (counts.changed_people)
    badges.push({ status: PersonStatus.CHANGED, label: `${counts.changed_people} changed` });
  if (counts.absent_memberships)
    badges.push({ status: PersonStatus.REMOVED, label: `${counts.absent_memberships} absent` });
  return badges.length ? badges : [{ status: PersonStatus.UNCHANGED, label: "Unchanged" }];
}

// Only open changesets can be selected. A published one is already live, and publishing it
// again would supersede it for nothing — the API drops it either way, so offering it is a lie.
export function selectableChangesetIds(items: Locality[]): string[] {
  return items.flatMap((locality) =>
    locality.review?.changeset_state === CHANGESET_OPEN ? [locality.review.changeset_id] : [],
  );
}

/** Page size for the review. Big enough that most batches are one page, small enough that a
 *  forty-locality import is not one scroll. */
export const REVIEW_PAGE_SIZE = 25;

export function pageOf<T>(items: T[], page: number): T[] {
  return items.slice(page * REVIEW_PAGE_SIZE, (page + 1) * REVIEW_PAGE_SIZE);
}

export function pageCount(items: unknown[]): number {
  return Math.max(1, Math.ceil(items.length / REVIEW_PAGE_SIZE));
}
