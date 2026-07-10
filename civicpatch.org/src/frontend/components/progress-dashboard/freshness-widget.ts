import './freshness-widget.css';
import { html } from 'lit-html';
import { computeStatusSegments, STATUS_LABELS } from './status-segments.js';
import { dateStringToFriendly } from '../../utils/date-utils.js';

interface DashboardState {
  civicpatch: {
    cutoff: string | null;
    status_counts: Record<string, number>;
    localities: { known: number };
  };
}

export interface FreshnessWidgetProps {
  stats: { states?: Record<string, DashboardState> } | null;
  state: string;
}

export function renderFreshnessWidget({ stats, state }: FreshnessWidgetProps) {
  const stateStats = stats?.states?.[state];
  if (!stateStats) return html``;

  const { cutoff, status_counts: statusCounts, localities } = stateStats.civicpatch;
  const segments = computeStatusSegments(statusCounts);

  return html`
    <div class="freshness-widget">
      <p class="freshness-widget__title">
        Progress — ${state.toUpperCase()} — ${localities.known} municipalities
      </p>
      ${cutoff
        ? html`<p class="freshness-widget__cutoff">Fresh = scraped after ${dateStringToFriendly(cutoff)}</p>`
        : ''}
      <div class="freshness-widget__bar">
        ${segments.map(
          (s) => html`<div
            class="freshness-widget__segment"
            style="width:${s.percent}%; background:var(--civ-status-${s.key})"
            title="${STATUS_LABELS[s.key]}: ${s.count}"
          ></div>`,
        )}
      </div>
      <div class="freshness-widget__legend">
        ${segments.map(
          (s) => html`<span class="freshness-widget__legend-item">
            <span class="freshness-widget__legend-dot" style="background:var(--civ-status-${s.key})"></span>
            <span class="freshness-widget__legend-count">${s.count}</span>
            ${STATUS_LABELS[s.key]}
          </span>`,
        )}
      </div>
    </div>
  `;
}
