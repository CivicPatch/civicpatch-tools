// `formatUsd` is the only pure thing in the spend column, and it is where the column can lie:
// one scrape costs a fraction of a cent, so a flat 2dp renders the whole table as $0.00.

import { describe, expect, it } from "vitest";

import {
  costPerScrapeOf,
  formatChange,
  formatUsd,
  spendChangeOf,
  spendOf,
  type StateSpend,
} from "../pages/changeset-summaries-page/spend.ts";

describe("formatUsd", () => {
  it("keeps a sub-cent figure visible instead of rounding it to nothing", () => {
    // The real dev figure for one Ellensburg scrape, 2026-09-05.
    expect(formatUsd("0.00221606")).toBe("$0.0022");
  });

  it("shows small amounts to four places", () => {
    expect(formatUsd("0.0425")).toBe("$0.0425");
    expect(formatUsd("0.99")).toBe("$0.9900");
  });

  it("switches to two places at a dollar", () => {
    expect(formatUsd("1")).toBe("$1.00");
    expect(formatUsd("18.4212")).toBe("$18.42");
  });

  it("reads the value as a string, so the exact decimal survives the wire", () => {
    // Pydantic serialises Decimal as text. Parsing early is what would lose this.
    expect(formatUsd("0.10")).toBe("$0.1000");
  });
});

const spend = (over: Partial<StateSpend> = {}): StateSpend => ({
  state: "wa",
  spend_usd: null,
  prior_spend_usd: null,
  cost_per_scrape_usd: null,
  ...over,
});

describe("sort accessors", () => {
  it("sorts a state that spent nothing as zero", () => {
    // Sorting only. The display never shows 0 — there it would claim a free scrape.
    expect(spendOf(undefined)).toBe(0);
    expect(costPerScrapeOf(spend())).toBe(0);
  });

  it("ranks a state that started spending above one that never did", () => {
    expect(spendChangeOf(spend({ spend_usd: "5.00" }))).toBeGreaterThan(
      spendChangeOf(undefined),
    );
  });

  it("ranks a state that stopped spending below one that never did", () => {
    // The drop is the signal — it has to sort somewhere, and below flat is the honest place.
    expect(spendChangeOf(spend({ prior_spend_usd: "5.00" }))).toBe(-5);
  });

  it("measures the change in dollars, not as a ratio", () => {
    // A tenfold rise on a fifth of a cent must not outrank a state that quietly added $40.
    const tenfold = spendChangeOf(spend({ spend_usd: "0.02", prior_spend_usd: "0.002" }));
    expect(spendChangeOf(spend({ spend_usd: "40.00" }))).toBeGreaterThan(tenfold);
  });
});

describe("formatChange", () => {
  it("signs a rise and a fall, because a fall is as worth seeing", () => {
    expect(formatChange(5)).toBe("+$5.00");
    expect(formatChange(-5)).toBe("−$5.00");
  });

  it("says flat in words rather than as a zero to be read", () => {
    expect(formatChange(0)).toBe("unchanged");
  });
});
