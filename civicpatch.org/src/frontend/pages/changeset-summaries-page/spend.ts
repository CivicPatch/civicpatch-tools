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

// One scrape costs a fraction of a cent, so dollars are the wrong unit for most of this page:
// `$0.00222` is five characters of leading zero before anything informative. Under a dollar the
// figure reads in cents, where the same number is `0.22¢`.
//
// The threshold is a dollar rather than a cent because mixing `$0.04` and `4.25¢` in one column
// is harder to scan than either alone.
export function formatUsd(value: string): string {
  const n = Number(value);
  if (n >= 1) return `$${n.toFixed(2)}`;
  return `${(n * 100).toFixed(2)}¢`;
}

// Signed, because a fall is as worth seeing as a rise. Exactly flat says so in words — `+0.00¢`
// is a number that has to be read to find out it says nothing.
export const formatChange = (change: number) =>
  change === 0
    ? "unchanged"
    : `${change > 0 ? "+" : "−"}${formatUsd(String(Math.abs(change)))}`;
