import {
  CHANGESET_OPEN,
  type ReviewJurisdiction,
  type ChangeCounts,
} from "./import-types.js";

export const REVIEW_FILTER = Object.freeze({
  HAS_ABSENT: "has-absent",
  HAS_ADDED: "has-added",
  UNCHANGED: "unchanged",
});
export type ReviewFilter = (typeof REVIEW_FILTER)[keyof typeof REVIEW_FILTER];

function isUnchanged(counts: ChangeCounts): boolean {
  return !counts.added_people && !counts.changed_people && !counts.absent_memberships;
}

// Lower is shown first: absences need the closest look, then new people, then edits.
function changeRank(counts: ChangeCounts): number {
  if (counts.absent_memberships) return 0;
  if (counts.added_people) return 1;
  if (counts.changed_people) return 2;
  return 3;
}

export function byChangeRank(
  jurisdictions: ReviewJurisdiction[],
): ReviewJurisdiction[] {
  return [...jurisdictions].sort(
    (a, b) =>
      changeRank(a.change_counts) - changeRank(b.change_counts) ||
      a.name.localeCompare(b.name),
  );
}

function matches(counts: ChangeCounts, filter: ReviewFilter): boolean {
  if (filter === REVIEW_FILTER.HAS_ABSENT) return counts.absent_memberships > 0;
  if (filter === REVIEW_FILTER.HAS_ADDED) return counts.added_people > 0;
  return isUnchanged(counts);
}

// No filter picked shows everything; several picked show a town matching any of them.
export function filtered(
  jurisdictions: ReviewJurisdiction[],
  filters: ReviewFilter[],
): ReviewJurisdiction[] {
  if (!filters.length) return jurisdictions;
  return jurisdictions.filter((jurisdiction) =>
    filters.some((filter) => matches(jurisdiction.change_counts, filter)),
  );
}

// "2 added, 1 absent" — only what is non-zero; empty when nothing changed.
export function changeSummary(counts: ChangeCounts): string {
  const parts = [];
  if (counts.added_people) parts.push(`${counts.added_people} added`);
  if (counts.changed_people) parts.push(`${counts.changed_people} changed`);
  if (counts.absent_memberships) parts.push(`${counts.absent_memberships} absent`);
  return parts.join(", ");
}

// Only open changesets can be selected. A published one is already live, and publishing it
// again would supersede it for nothing — the API drops it either way, so offering it is a lie.
export function selectableChangesetIds(
  jurisdictions: ReviewJurisdiction[],
): string[] {
  return jurisdictions
    .filter((jurisdiction) => jurisdiction.changeset_state === CHANGESET_OPEN)
    .map((jurisdiction) => jurisdiction.changeset_id);
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
