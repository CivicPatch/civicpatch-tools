// The rules the source comparison renders by. Shared, because this table is
// drawn in two places — the review drawer and the queue page's PR card — and
// when each kept its own copy they drifted: one tinted a dropped official green
// while the other got it right.

const EXISTING_SOURCE = "existing";

const ORIGIN_SOURCE_LABEL_BY_KEY: Record<string, string> = {
  google_gemini: "Google Gemini",
  [EXISTING_SOURCE]: "Existing",
};

// origin_source says where the comparison's baseline came from. The collector
// uses people already in the DB when it finds any, and skips Gemini — so
// "existing" is the only value that means there was a previous scrape to
// compare against. Anything else and Gemini supplied the baseline itself, which
// makes the table a first capture rather than a diff.
export function hasPriorScrape(originSource: string | null | undefined): boolean {
  return originSource === EXISTING_SOURCE;
}

// A pipeline that grows a new origin source should still render a usable column
// header rather than an empty one.
export function originSourceLabel(originSource: string | null | undefined): string {
  return (originSource && ORIGIN_SOURCE_LABEL_BY_KEY[originSource]) || "Research";
}

// The baseline side of the comparison: the previous scrape when there was one,
// otherwise whatever supplied the baseline instead.
export function baselineColumnLabel(originSource: string | null | undefined): string {
  return hasPriorScrape(originSource) ? "Last scrape" : originSourceLabel(originSource);
}

export interface SourceRow {
  name: string;
  in_research: boolean;
  in_data: boolean;
}

// Which way the roster moved, in the diff convention: red for a name that was in
// the baseline and is not in this scrape, green for one that has appeared.
// Agreeing on both sides needs no decision, so it gets no tint.
//
// `in_research` is the BASELINE, not a fresh discovery. build_review_summary
// names these same two conditions ABSENT_PERSON and NEW_PERSON; the
// tints follow it, so the table cannot contradict the checklist beside it.
//
// Green is direction, not approval: an extra official is still an issue someone
// has to decide about.
export function sourceRowClass(row: SourceRow): string {
  if (row.in_research && !row.in_data) return "people-by-source__row--dropped";
  if (!row.in_research && row.in_data) return "people-by-source__row--added";
  return "";
}
