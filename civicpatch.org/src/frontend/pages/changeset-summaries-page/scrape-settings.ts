// The cadence and budget block, and the pure formatting it needs.

import { formatUsd } from "./spend.js";

export interface StateScrapePanel {
  state: string;
  cadence_days: number | null;
  cadence_anchor: string | null;
  next_run_at: string | null;
  pipeline_run_cap_usd: string | null;
  monthly_cap_usd: string | null;
  global_monthly_cap_usd: string | null;
  spent_this_month_usd: string;
  global_spent_this_month_usd: string;
  cap_reached: string | null;
  cost_cap_hits_this_month: number;
  candidates_due: number;
}

export const MANUAL = "manual";

export function describeCadence(panel: StateScrapePanel): string {
  if (panel.cadence_days === null) return MANUAL;
  const days = panel.cadence_days;
  return days === 1 ? "daily" : `every ${days} days`;
}

// Sep 1 at 30 days gives Sep 1, Oct 1, Nov 1 — and Aug 2 before that. Not a start date.
export function describeAnchor(panel: StateScrapePanel): string {
  return panel.cadence_anchor ? `landing on ${panel.cadence_anchor}` : "";
}

export function describeNextRun(nextRunAt: string | null, now: Date): string {
  if (nextRunAt === null) return "no schedule";
  const days = Math.round((new Date(nextRunAt).getTime() - now.getTime()) / 86_400_000);
  if (days <= 0) return "due now";
  return days === 1 ? "in 1 day" : `in ${days} days`;
}

// Null cap reads as "no ceiling", never $0.00 — $0 is a real setting meaning spend nothing.
export function describeBudget(spent: string, cap: string | null): string {
  const spentText = formatUsd(spent);
  return cap === null ? `${spentText} spent, no cap` : `${spentText} of ${formatUsd(cap)}`;
}

export interface MonthlyEstimate {
  passes_per_month: number;
  per_run_usd: string;
  monthly_usd: string;
  over_cap: boolean;
}

// Display only: cost per run varies with page count and chunking, so this says "about" and
// enforcement counts real spend instead.
export function estimateMonthlyCost(
  cadenceDays: number | null,
  candidates: number,
  perRunCapUsd: string | null,
  monthlyCapUsd: string | null = null,
  fallbackPerRunUsd = "0.05",
): MonthlyEstimate | null {
  if (cadenceDays === null || candidates === 0) return null;
  const perRun = Number(perRunCapUsd ?? fallbackPerRunUsd);
  const passes = Math.max(1, Math.round(30 / cadenceDays));
  const monthly = passes * candidates * perRun;
  return {
    passes_per_month: passes,
    per_run_usd: String(perRun),
    monthly_usd: String(monthly),
    over_cap: monthlyCapUsd !== null && monthly > Number(monthlyCapUsd),
  };
}

export interface GlobalScrapePanel {
  monthly_cap_usd: string | null;
  spent_this_month_usd: string;
  state_monthly_caps_usd: string;
}

// State caps may add up past the global one: they are ceilings, not reservations.
export function describeStateCaps(panel: GlobalScrapePanel): string {
  const caps = `${formatUsd(panel.state_monthly_caps_usd)} in state caps`;
  if (panel.monthly_cap_usd === null) return caps;
  return Number(panel.state_monthly_caps_usd) > Number(panel.monthly_cap_usd)
    ? `${caps}, over the cap`
    : caps;
}
