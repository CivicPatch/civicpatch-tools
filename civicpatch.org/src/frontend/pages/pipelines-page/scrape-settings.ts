// The cadence and budget block, and the pure formatting it needs.

// Four places under a dollar: a run costs a fraction of a cent, and $0.00 hides it.
export function formatUsd(value: string): string {
  const n = Number(value);
  return n >= 1 ? `$${n.toFixed(2)}` : `$${n.toFixed(4)}`;
}

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
  // Null means no runs this month, never a free one.
  cost_per_run_this_month_usd: string | null;
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

export function describePerRun(costPerRun: string | null, cap: string | null): string {
  if (costPerRun === null) return cap === null ? "no cap" : `${formatUsd(cap)} cap`;
  const costText = formatUsd(costPerRun);
  return cap === null ? `${costText}, no cap` : `${costText} of ${formatUsd(cap)}`;
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
  // Month to date, every state. Null means no runs to average.
  cost_per_run_this_month_usd: string | null;
  seconds_per_run_this_month: number | null;
  pipeline_run_concurrency: number;
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours}h` : `${hours}h ${rest}m`;
}

// Wall-clock: a batch runs `concurrency` at a time, so the due list takes that many rounds.
// Total: every run's time added up, which is what counts against rate limits.
export interface NextPass {
  cost: string;
  wall_clock: string;
  total: string;
}

// Empty strings when nothing is due or there are no runs to average: never a $0 or 0s estimate.
export function describeNextPass(candidatesDue: number, fleet: GlobalScrapePanel): NextPass {
  const cost = fleet.cost_per_run_this_month_usd;
  const seconds = fleet.seconds_per_run_this_month;
  const rounds = Math.ceil(candidatesDue / fleet.pipeline_run_concurrency);
  const due = candidatesDue > 0;
  return {
    cost: due && cost !== null ? formatUsd(String(candidatesDue * Number(cost))) : "",
    wall_clock: due && seconds !== null ? formatDuration(rounds * seconds) : "",
    total: due && seconds !== null ? formatDuration(candidatesDue * seconds) : "",
  };
}

// State caps may add up past the global one: they are ceilings, not reservations.
export function describeStateCaps(panel: GlobalScrapePanel): string {
  const caps = `${formatUsd(panel.state_monthly_caps_usd)} in state caps`;
  if (panel.monthly_cap_usd === null) return caps;
  return Number(panel.state_monthly_caps_usd) > Number(panel.monthly_cap_usd)
    ? `${caps}, over the cap`
    : caps;
}
