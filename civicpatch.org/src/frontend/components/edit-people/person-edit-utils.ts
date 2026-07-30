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

export const DIVISION_AT_LARGE = "at_large";
export const DIVISION_OTHER = "other";

export type DivisionType =
  | typeof DIVISION_AT_LARGE
  | "council_district"
  | "ward"
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

  if (label === "council_district" || label === "ward") return { type: label, value };
  if (label === "place") return { type: DIVISION_AT_LARGE, value: "" };
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
export type Person = {
  id: string;
  name?: string;
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

export type Draft = {
  name: string;
  officeName: string;
  divisionType: DivisionType;
  divisionValue: string;
  startDate: DateParts;
  endDate: DateParts;
  otherNames: string[];
  phones: string[];
  emails: string[];
  urls: string[];
  sourceUrls: string[];
  linkedId: string; // staged "link to existing record" — applied as `id` on save
};

export function toDraft(person: Person, jurisdictionOcdid: string | null | undefined): Draft {
  const division = parseDivision(person.office?.division_ocdid, jurisdictionOcdid);
  return {
    name: person.name ?? "",
    officeName: person.office?.name ?? "",
    divisionType: division.type,
    divisionValue: division.value,
    startDate: parseDate(person.start_date),
    endDate: parseDate(person.end_date),
    otherNames: person.other_names ?? [],
    phones: person.phones ?? [],
    emails: person.emails ?? [],
    urls: person.urls ?? [],
    sourceUrls: person.source_urls ?? [],
    linkedId: "",
  };
}

// Only genuinely-changed fields (vs the original person), so untouched rows stay
// clean. Nested office is sent as a whole object — matching the table's data-change
// contract — and a legacy "other" division is preserved as-is.
export function buildUpdates(person: Person, draft: Draft, jurisdictionOcdid: string): Record<string, unknown> {
  const updates: Record<string, unknown> = {};
  const set = (field: string, value: unknown, original: unknown) => {
    if (JSON.stringify(value) !== JSON.stringify(original)) updates[field] = value;
  };

  set("name", draft.name, person.name ?? "");
  set("start_date", serializeDate(draft.startDate) || null, person.start_date ?? null);
  set("end_date", serializeDate(draft.endDate) || null, person.end_date ?? null);
  set("other_names", draft.otherNames, person.other_names ?? []);
  set("phones", draft.phones, person.phones ?? []);
  set("emails", draft.emails, person.emails ?? []);
  set("urls", draft.urls, person.urls ?? []);
  set("source_urls", draft.sourceUrls, person.source_urls ?? []);

  const division_ocdid = draft.divisionType === DIVISION_OTHER
    ? person.office?.division_ocdid ?? ""
    : buildDivisionOcdid(jurisdictionOcdid, draft.divisionType, draft.divisionValue);
  set("office", { ...(person.office ?? {}), name: draft.officeName, division_ocdid }, person.office ?? {});

  // linking just re-points the id; usePeopleState handles the re-ID + collapse
  if (draft.linkedId && draft.linkedId !== person.id) updates.id = draft.linkedId;

  return updates;
}
