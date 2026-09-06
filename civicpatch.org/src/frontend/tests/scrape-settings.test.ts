import { describe, expect, it } from "vitest";

import {
  describeStateCaps,
  describeBudget,
  describeCadence,
  describeNextRun,
  estimateMonthlyCost,
  type StateScrapePanel,
} from "../pages/changeset-summaries-page/scrape-settings.ts";

const panel = (over: Partial<StateScrapePanel> = {}): StateScrapePanel => ({
  state: "wa",
  cadence_days: null,
  cadence_anchor: null,
  next_run_at: null,
  pipeline_run_cap_usd: null,
  monthly_cap_usd: null,
  global_monthly_cap_usd: null,
  spent_this_month_usd: "0",
  global_spent_this_month_usd: "0",
  cap_reached: null,
  cost_cap_hits_this_month: 0,
  candidates_due: 0,
  ...over,
});

describe("describeCadence", () => {
  it("says manual when there is no cadence", () => {
    expect(describeCadence(panel())).toBe("manual");
  });

  it("does not say 'every 1 days'", () => {
    expect(describeCadence(panel({ cadence_days: 1 }))).toBe("daily");
    expect(describeCadence(panel({ cadence_days: 30 }))).toBe("every 30 days");
  });
});

describe("describeNextRun", () => {
  const now = new Date("2026-09-05T00:00:00Z");

  it("says there is no schedule rather than inventing a date", () => {
    expect(describeNextRun(null, now)).toBe("no schedule");
  });

  it("reads a past boundary as due now, not as a negative", () => {
    expect(describeNextRun("2026-09-04T00:00:00Z", now)).toBe("due now");
  });

  it("counts whole days and does not say '1 days'", () => {
    expect(describeNextRun("2026-09-06T00:00:00Z", now)).toBe("in 1 day");
    expect(describeNextRun("2026-09-12T00:00:00Z", now)).toBe("in 7 days");
  });
});

describe("describeBudget", () => {
  it("says no cap rather than showing a zero ceiling", () => {
    // $0 is a real setting meaning spend nothing; null means no ceiling at all.
    expect(describeBudget("1.50", null)).toBe("$1.50 spent, no cap");
  });

  it("shows spend against the cap when there is one", () => {
    expect(describeBudget("1.50", "12.00")).toBe("$1.50 of $12.00");
  });

  it("keeps a zero cap visible instead of reading it as absent", () => {
    expect(describeBudget("0", "0")).toBe("$0.0000 of $0.0000");
  });
});

describe("estimateMonthlyCost", () => {
  it("is absent for a manual state, which has no passes to cost", () => {
    expect(estimateMonthlyCost(null, 41, "0.20")).toBeNull();
  });

  it("is absent when nothing is due, rather than estimating zero", () => {
    expect(estimateMonthlyCost(30, 0, "0.20")).toBeNull();
  });

  it("prices a pass at the state's own cap, not the default", () => {
    const e = estimateMonthlyCost(30, 10, "0.05")!;
    expect(e.passes_per_month).toBe(1);
    expect(e.monthly_usd).toBe("0.5");
  });

  it("falls back to the package default when the state sets no cap", () => {
    expect(estimateMonthlyCost(30, 10, null)!.per_run_usd).toBe("0.05");
  });

  it("counts more than one pass for a short cadence", () => {
    expect(estimateMonthlyCost(7, 10, "0.20")!.passes_per_month).toBe(4);
  });

  it("never estimates less than one pass a month", () => {
    // A 90-day cadence still costs a pass in the month it falls in.
    expect(estimateMonthlyCost(90, 10, "0.20")!.passes_per_month).toBe(1);
  });

  it("says when the estimate exceeds the cap without refusing it", () => {
    // A projection is too coarse to refuse a run on; enforcement counts real spend.
    expect(estimateMonthlyCost(30, 100, "0.20", "5.00")!.over_cap).toBe(true);
    expect(estimateMonthlyCost(30, 10, "0.20", "5.00")!.over_cap).toBe(false);
  });
});

describe("describeStateCaps", () => {
  const g = (over = {}) => ({
    monthly_cap_usd: null,
    spent_this_month_usd: "0",
    state_monthly_caps_usd: "0",
    ...over,
  });

  it("does not compare against a cap that is not set", () => {
    expect(describeStateCaps(g({ state_monthly_caps_usd: "120" }))).toBe("$120.00 in state caps");
  });

  it("says when the state caps exceed the cap without treating it as an error", () => {
    // Ceilings, not reservations — refusing this would be the allocation model the plan rejected.
    expect(describeStateCaps(g({ state_monthly_caps_usd: "120", monthly_cap_usd: "40" }))).toBe(
      "$120.00 in state caps, over the cap",
    );
  });

  it("is quiet when the allocation fits", () => {
    expect(describeStateCaps(g({ state_monthly_caps_usd: "20", monthly_cap_usd: "40" }))).toBe(
      "$20.00 in state caps",
    );
  });
});
