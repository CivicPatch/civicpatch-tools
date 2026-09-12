// Upcoming election dates — a hand-maintained YAML file for now (GET /api/v1/elections), not
// synced from anywhere yet. One row per state, one chip per election: date + title, no click
// handler yet but real <button>s — the natural place to hang a later "open this entry" action.

import { html, nothing } from "lit-html";

export interface Election {
  date: string;
  state: string;
  title: string;
  note: string | null;
}

const ALERT_WINDOW_DAYS = 60;

const daysUntil = (date: string): number => {
  const ms = new Date(`${date}T00:00:00Z`).getTime() - Date.now();
  return Math.floor(ms / (1000 * 60 * 60 * 24));
};

export const isSoon = (date: string) => daysUntil(date) <= ALERT_WINDOW_DAYS;

const shortDate = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "2-digit",
    timeZone: "UTC",
  });

// Grouped, not filtered — a state with no elections just never gets a row, same as a state
// with no calendar activity in the rollup above never getting a day cell.
export function groupByState(elections: Election[]): Map<string, Election[]> {
  const byState = new Map<string, Election[]>();
  for (const entry of [...elections].sort((a, b) => a.date.localeCompare(b.date))) {
    const rows = byState.get(entry.state) ?? [];
    rows.push(entry);
    byState.set(entry.state, rows);
  }
  return byState;
}

function renderChip(entry: Election) {
  return html`
    <button class="cs-echip ${isSoon(entry.date) ? "cs-echip--alert" : ""}" title=${entry.note ?? ""}>
      <span class="cs-echip__date">${shortDate(entry.date)}</span>
      <span class="cs-echip__title">${entry.title}</span>
    </button>
  `;
}

function renderRow(state: string, entries: Election[]) {
  const alert = entries.some((entry) => isSoon(entry.date)) ? "cs-figure--alert" : "";
  return html`
    <div class="cs-row">
      <span class="cs-row__state">${state}</span>
      <span class="cs-figure ${alert}">
        <span class="cs-figure__n">${entries.length}</span>
        <span class="cs-figure__label">upcoming</span>
      </span>
      <span class="cs-echips">${entries.map(renderChip)}</span>
    </div>
  `;
}

export function renderElections(elections: Election[]) {
  if (!elections.length) return nothing;
  const byState = groupByState(elections);
  const states = [...byState.keys()].sort();
  return html`
    <section class="panel cs-elections">
      <div class="panel__cap">
        <b>elections</b>
        <span class="panel__cap-right">${elections.length} upcoming</span>
      </div>
      ${states.map((state) => renderRow(state, byState.get(state) ?? []))}
    </section>
  `;
}
