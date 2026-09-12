import '../panel/panel.css';
import './freshness-widget.css';
import { html } from 'lit-html';
import { computeStatusSegments, STATUS_LABELS } from './status-segments.js';
import { dateStringToFriendly } from '../../utils/date-utils.js';
import { stateNameForCode } from '../ocdid-utils.js';

interface Tier {
  known: number;
  status_counts: Record<string, number>;
}

interface DashboardState {
  civicpatch: {
    cutoff: string | null;
    municipalities: Tier;
    counties: Tier;
  };
}

export interface FreshnessWidgetProps {
  stats: { states?: Record<string, DashboardState> } | null;
  state: string;
}

// A tier with no scraped/collected officials at all is one this state doesn't treat as
// a scrape target (e.g. counties, in every state but Hawaii) — showing it would just be
// a permanent wall of "no data".
export function hasAnyCoverage(tier: Tier): boolean {
  return tier.status_counts.fresh + tier.status_counts.stale > 0;
}

function renderTierBar(tier: Tier, label: string) {
  const segments = computeStatusSegments(tier.status_counts);
  return html`
    <div class="freshness-widget__tier">
      <p class="freshness-widget__tier-title">${tier.known} ${label}</p>
      <div class="freshness-widget__bar">
        ${segments.map(
          (s) => html`<div
            class="freshness-widget__segment"
            style="width:${s.percent}%; background:var(--status-${s.key})"
            title="${STATUS_LABELS[s.key]}: ${s.count}"
          ></div>`,
        )}
      </div>
      <div class="freshness-widget__legend">
        ${segments.map(
          (s) => html`<span class="freshness-widget__legend-item">
            <span class="freshness-widget__legend-dot" style="background:var(--status-${s.key})"></span>
            <span class="freshness-widget__legend-count">${s.count}</span>
            ${STATUS_LABELS[s.key]}
          </span>`,
        )}
      </div>
    </div>
  `;
}

export function renderFreshnessWidget({ stats, state }: FreshnessWidgetProps) {
  const stateStats = stats?.states?.[state];
  if (!stateStats) return html``;

  const { cutoff, municipalities, counties } = stateStats.civicpatch;
  const stateLabel = stateNameForCode(state) || state.toUpperCase();

  return html`
    <div class="panel">
      <div class="panel__cap">
        <b>${stateLabel} progress</b>
        ${cutoff
          ? html`<span class="panel__cap-right">Fresh = scraped after ${dateStringToFriendly(cutoff)}</span>`
          : ''}
      </div>
      ${renderTierBar(municipalities, 'municipalities')}
      ${hasAnyCoverage(counties) ? renderTierBar(counties, 'counties') : ''}
    </div>
  `;
}
