// What scraping cost, per state. Its own module so the formatting can be tested without
// dragging the page component — and its own type rather than fields on `StateRollup`, because
// this arrives from a different endpoint under a different permission.
//
// `spend_usd` is a **string**: Pydantic serialises Decimal as text, which is what keeps a
// fraction of a cent exact. Parse it at the point of display, never earlier.
export interface StateSpend {
  state: string;
  // Null means the state spent nothing in that window. A state absent from the map spent
  // nothing in either. Neither is zero: nothing is not the same as free.
  spend_usd: string | null;
  prior_spend_usd: string | null;
  cost_per_scrape_usd: string | null;
}

// Sorting only. A state that spent nothing sorts as 0; the display never does, because there
// 0 would be a claim that it scraped for free.
const amount = (value: string | null): number => (value === null ? 0 : Number(value));

export const spendOf = (spend: StateSpend | undefined) =>
  spend ? amount(spend.spend_usd) : 0;

export const costPerScrapeOf = (spend: StateSpend | undefined) =>
  spend ? amount(spend.cost_per_scrape_usd) : 0;

// Absolute dollars, not a ratio: a tenfold rise on a fifth of a cent is not the thing anyone
// needs to see first, and a ratio would rank it above a state that quietly added $40.
export const spendChangeOf = (spend: StateSpend | undefined) =>
  spend ? amount(spend.spend_usd) - amount(spend.prior_spend_usd) : 0;

// Four places under a dollar: a run costs a fraction of a cent, and $0.00 hides it.
export function formatUsd(value: string): string {
  const n = Number(value);
  return n >= 1 ? `$${n.toFixed(2)}` : `$${n.toFixed(4)}`;
}

// Signed, because a fall is as worth seeing as a rise. Flat says so in words, not as a zero.
export const formatChange = (change: number) =>
  change === 0
    ? "unchanged"
    : `${change > 0 ? "+" : "−"}${formatUsd(String(Math.abs(change)))}`;
