import { REVIEW_PENDING, type ReviewJurisdiction } from "./import-types.js";

// Only pending towns can be selected. A published one is already live, and publishing it again
// would supersede it for nothing — the API drops it either way, so offering it is a lie.
export function selectableOcdids(
  jurisdictions: ReviewJurisdiction[],
): string[] {
  return jurisdictions
    .filter((jurisdiction) => jurisdiction.review_status === REVIEW_PENDING)
    .map((jurisdiction) => jurisdiction.jurisdiction_ocdid);
}

export function toggleSelection(selected: string[], ocdid: string): string[] {
  return selected.includes(ocdid)
    ? selected.filter((each) => each !== ocdid)
    : [...selected, ocdid];
}
