// The rules the source comparison renders by. Shared, because this table is
// drawn in two places — the review drawer and the queue page's PR card — and
// when each kept its own copy they drifted: one tinted a dropped official green
// while the other got it right.

export interface SourceRow {
  name: string;
  in_research: boolean;
  in_data: boolean;
}

// The baseline is the jurisdiction's published people, so nobody on it means
// nothing was published before this scrape.
export function hasPriorScrape(rows: SourceRow[]): boolean {
  return rows.some((row) => row.in_research);
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
