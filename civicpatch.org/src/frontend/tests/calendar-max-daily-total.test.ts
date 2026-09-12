// maxDailyTotal is the one pure function behind the calendar strip's per-day bar height — the
// rest of calendar.ts is markup. Testing the states the plan actually needs instead of render.

import { describe, expect, it } from "vitest";

import {
  dayKey,
  maxDailyTotal,
  type CalendarDay,
} from "../pages/changeset-summaries-page/calendar.ts";

const day = (state: string, dayStr: string, overrides: Partial<CalendarDay> = {}): [string, CalendarDay] => [
  dayKey(state, dayStr),
  {
    state,
    day: dayStr,
    published: 0,
    to_review: 0,
    dismissed: 0,
    scrapes: 0,
    imports: 0,
    ...overrides,
  },
];

describe("maxDailyTotal", () => {
  it("is the busiest day's published+review+dismissed total", () => {
    const calendar = new Map([
      day("wa", "2026-09-01", { published: 2 }),
      day("wa", "2026-09-02", { published: 5, dismissed: 3 }),
      day("wa", "2026-09-03", { to_review: 1 }),
    ]);
    expect(maxDailyTotal(calendar, "wa", ["2026-09-01", "2026-09-02", "2026-09-03"])).toBe(8);
  });

  it("is 0 for a state with no days in the calendar", () => {
    const calendar = new Map([day("tx", "2026-09-01", { published: 4 })]);
    expect(maxDailyTotal(calendar, "wa", ["2026-09-01"])).toBe(0);
  });

  it("ignores days outside the given window even if present in the map", () => {
    const calendar = new Map([
      day("wa", "2026-08-01", { published: 100 }),
      day("wa", "2026-09-01", { published: 2 }),
    ]);
    expect(maxDailyTotal(calendar, "wa", ["2026-09-01"])).toBe(2);
  });
});
