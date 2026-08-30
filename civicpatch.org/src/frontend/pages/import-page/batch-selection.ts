import { REVIEW_PENDING, type ReviewJurisdiction } from "./import-types.js";

// Only pending localities can be selected. A published one is already live, and publishing it
// again would supersede it for nothing — the API drops it either way, so offering it is a lie.
export function selectableOcdids(
  jurisdictions: ReviewJurisdiction[],
): string[] {
  return jurisdictions
    .filter((jurisdiction) => jurisdiction.review_status === REVIEW_PENDING)
    .map((jurisdiction) => jurisdiction.jurisdiction_ocdid);
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

export function toggleSelection(selected: string[], ocdid: string): string[] {
  return selected.includes(ocdid)
    ? selected.filter((each) => each !== ocdid)
    : [...selected, ocdid];
}
