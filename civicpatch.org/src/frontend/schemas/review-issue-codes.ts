// Mirrors `shared/schemas.py` IssueCode: the issues a review card carries.
export const REVIEW_ISSUE_CODE = Object.freeze({
  ABSENT_PERSON: "absent_person",
  NEW_PERSON: "new_person",
  MOVED_PERSON: "moved_person",
  TOO_FEW_PEOPLE: "too_few_people",
  DUPLICATE_UNIQUE_ROLE: "duplicate_unique_role",
  DIVISION_NUMBERING_GAP: "division_numbering_gap",
  NOBODY_FOUND_IN_ORGANIZATION: "nobody_found_in_organization",
  NEW_POST: "new_post",
  UNCERTAIN_ORGANIZATION: "uncertain_organization",
  CHANGED_FIELD: "changed_field",
} as const);

// A card's issue chip, in a reviewer's words. A code with no entry shows de-underscored.
export const REVIEW_ISSUE_CHIP_LABEL: Partial<Record<string, string>> = {
  [REVIEW_ISSUE_CODE.TOO_FEW_PEOPLE]: "fewer people than expected",
  [REVIEW_ISSUE_CODE.DUPLICATE_UNIQUE_ROLE]: "two people, one seat",
  [REVIEW_ISSUE_CODE.DIVISION_NUMBERING_GAP]: "a numbered seat is missing",
  [REVIEW_ISSUE_CODE.NOBODY_FOUND_IN_ORGANIZATION]: "nobody found here",
  [REVIEW_ISSUE_CODE.UNCERTAIN_ORGANIZATION]: "check the organization",
};
