// Pure round-trip helpers for the person-edit modal: partial dates and the
// division OCD-ID. No DOM, no side effects.

export type DateParts = { year: string; month: string; day: string };

// Presentation constants for the Y/M/D controls, next to the parse/serialize
// pair they belong with so the modal and the diff can't drift apart.
export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const DAYS = Array.from({ length: 31 }, (_, i) => String(i + 1).padStart(2, "0"));
export const padDatePart = (n: number) => String(n).padStart(2, "0");

// A day with no month is meaningless, so clearing the month clears the day.
// Date parts cascade: a month is meaningless without a year, and a day without a
// month. Clearing a part therefore clears everything finer than it, so the record
// can never hold "March, no year".
export function setDatePart(parts: DateParts, key: keyof DateParts, value: string): DateParts {
  const next = { ...parts, [key]: value };
  if (key === "month" && !value) next.day = "";
  if (key === "year" && !value) {
    next.month = "";
    next.day = "";
  }
  return next;
}

// DivisionType values — what a seat represents. `at_large` and `other` are ours
// alone and never appear in an ocdid; the two below double as segment labels,
// which is what lets parseDivision return the label as a type.
export const DIVISION_AT_LARGE = "at_large";
export const DIVISION_OTHER = "other";
export const DIVISION_COUNCIL_DISTRICT = "council_district";
export const DIVISION_WARD = "ward";

// A segment label, not a DivisionType. A division ending at the place segment
// carries no district, so the seat covers the whole jurisdiction.
export const PLACE_LABEL = "place";

export type DivisionType =
  | typeof DIVISION_AT_LARGE
  | typeof DIVISION_COUNCIL_DISTRICT
  | typeof DIVISION_WARD
  | typeof DIVISION_OTHER;

export type Division = { type: DivisionType; value: string };

// "2023" | "2023-11" | "2023-11-15" | null -> parts (empty strings for missing)
export function parseDate(value: string | null | undefined): DateParts {
  const [year = "", month = "", day = ""] = (value ?? "").split("-");
  return { year, month, day };
}

// parts -> "2023" | "2023-11" | "2023-11-15" | "" (omit from the first empty part)
export function serializeDate({ year, month, day }: DateParts): string {
  if (!year) return "";
  if (!month) return year;
  if (!day) return `${year}-${month}`;
  return `${year}-${month}-${day}`;
}

// ocd-jurisdiction/country:us/state:co/place:denver/government
//   -> ocd-division/country:us/state:co/place:denver
export function jurisdictionToDivisionBase(jurisdictionOcdid: string | null | undefined): string {
  if (!jurisdictionOcdid) return "";
  return jurisdictionOcdid.replace(/^ocd-jurisdiction/, "ocd-division").replace(/\/government$/, "");
}

// division_ocdid -> {type, value}. At-large when it's exactly the
// jurisdiction's base division (no extra district/ward segment); otherwise
// recognizes council_district / ward; anything else (e.g. legacy precinct)
// is "other".
export function parseDivision(
  divisionOcdid: string | null | undefined,
  jurisdictionOcdid: string | null | undefined,
): Division {
  if (!divisionOcdid) return { type: DIVISION_AT_LARGE, value: "" };
  if (divisionOcdid === jurisdictionToDivisionBase(jurisdictionOcdid)) return { type: DIVISION_AT_LARGE, value: "" };

  const lastSegment = divisionOcdid.split("/").pop() ?? "";
  const [label, value = ""] = lastSegment.split(":");

  if (label === DIVISION_COUNCIL_DISTRICT || label === DIVISION_WARD)
    return { type: label, value };
  if (label === PLACE_LABEL) return { type: DIVISION_AT_LARGE, value: "" };
  return { type: DIVISION_OTHER, value: "" };
}

// {type, value} + a base division -> division_ocdid. At-large is just the base.
// Split from buildDivisionOcdid because the diff has to fall back to the person's
// existing division as the base when it has no jurisdiction to derive one from.
export function buildDivisionFromBase(base: string, type: DivisionType, value: string): string {
  if (type === DIVISION_AT_LARGE || type === DIVISION_OTHER) return base;
  return `${base}/${type}:${value}`;
}

// {type, value} + jurisdiction -> division_ocdid.
export function buildDivisionOcdid(
  jurisdictionOcdid: string | null | undefined,
  type: DivisionType,
  value: string,
): string {
  return buildDivisionFromBase(jurisdictionToDivisionBase(jurisdictionOcdid), type, value);
}

export type Office = { name?: string; division_ocdid?: string | null; [k: string]: unknown };
// One post a person holds, as the API sends it. `post_label` is the post's own name and
// `label` is what the source said beyond it — the two halves of how a post reads.
export type PersonMembership = {
  post_id: string;
  role_id: string;
  role_label: string;
  division_ocdid: string;
  label: string | null;
  post_label: string | null;
  source_labels: string[];
};

export type Person = {
  id: string;
  name?: string;
  // Where they serve. `office` is the joined string this replaces, still sent while the
  // review surfaces move off it.
  memberships?: PersonMembership[];
  labels?: string[];
  office?: Office;
  start_date?: string | null;
  end_date?: string | null;
  other_names?: string[];
  phones?: string[];
  emails?: string[];
  urls?: string[];
  source_urls?: string[];
  jurisdiction_ocdid?: string;
  // The diff reads both: a stored record carries cdn_image, a freshly scraped
  // one only image (see diffValue in diff-model).
  image?: string | null;
  cdn_image?: string | null;
};
