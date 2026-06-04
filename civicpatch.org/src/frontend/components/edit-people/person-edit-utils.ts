// Pure round-trip helpers for the person-edit modal: partial dates and the
// division OCD-ID. No DOM, no side effects.

export type DateParts = { year: string; month: string; day: string };

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

// division_ocdid -> {type, value}. Recognizes council_district / ward; a bare
// place segment is at-large; anything else (e.g. legacy precinct) is "other".
export function parseDivision(divisionOcdid: string | null | undefined): Division {
  if (!divisionOcdid) return { type: DIVISION_AT_LARGE, value: "" };

  const lastSegment = divisionOcdid.split("/").pop() ?? "";
  const [label, value = ""] = lastSegment.split(":");

  if (label === "council_district" || label === "ward") return { type: label, value };
  if (label === "place") return { type: DIVISION_AT_LARGE, value: "" };
  return { type: DIVISION_OTHER, value: "" };
}

// {type, value} + jurisdiction -> division_ocdid. At-large is just the base.
export function buildDivisionOcdid(
  jurisdictionOcdid: string | null | undefined,
  type: DivisionType,
  value: string,
): string {
  const base = jurisdictionToDivisionBase(jurisdictionOcdid);
  if (type === DIVISION_AT_LARGE || type === DIVISION_OTHER) return base;
  return `${base}/${type}:${value}`;
}

export type Office = { name?: string; division_ocdid?: string; [k: string]: unknown };
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
};

export function toDraft(person: Person): Draft {
  const division = parseDivision(person.office?.division_ocdid);
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

  return updates;
}
