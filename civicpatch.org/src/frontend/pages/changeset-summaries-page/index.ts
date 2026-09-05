// Changeset activity across every state, for maintainers and up: what is waiting on a reviewer
// and how long it has waited, what ran each day, and what came of it.
//
// Not a scrape page, and deliberately not named one — `sheet_import` is 76% of changesets and
// `scrape` 24%, so labelling these figures "scrapes" would misreport three quarters of them.

import { component, useEffect, useState } from "haunted";
import { html, nothing } from "lit-html";
import "./changeset-summaries.css";
import { fetchStateCalendar, fetchStateRollup } from "../../api.js";
import { useAuth } from "../../hooks/useAuth.js";
import {
  dayKey,
  renderDay,
  renderScale,
  windowDays,
  type CalendarDay,
} from "./calendar.js";
import "./state-section.ts";
import "./bucket-modal.ts";

const WINDOW_DAYS = 30;

export interface StateRollup {
  state: string;
  running: number;
  to_review: number;
  oldest_days: number;
  published: number;
  dismissed: number;
  failed_runs: number;
  roster_edits: number;
  last_run_at: string | null;
}

// A queue is not a problem because it is deep; it is a problem because something in it is old.
const STALE_DAYS = 7;

const SORTS: Record<string, (a: StateRollup, b: StateRollup) => number> = {
  queue: (a, b) => b.to_review - a.to_review,
  oldest: (a, b) => b.oldest_days - a.oldest_days,
  dismissed: (a, b) => b.dismissed - a.dismissed,
  name: (a, b) => a.state.localeCompare(b.state),
};

const CHIPS = [
  { key: "queue", label: "To review" },
  { key: "oldest", label: "Longest waiting" },
  { key: "dismissed", label: "Dismissed" },
  { key: "name", label: "State" },
];

// The age is no longer its own column, so it rides on the queue figure — which is the only
// thing it says anything about, and what the red tint is already reacting to.
const queueTitle = (row: StateRollup) =>
  row.to_review
    ? `${row.to_review} waiting, the oldest for ${row.oldest_days} days`
    : "nothing waiting";

function renderFigure(value: number, label: string, tone = "", title = label) {
  const quiet = value === 0 ? " cs-figure--quiet" : "";
  return html`
    <span class="cs-figure ${tone}${quiet}" title="${title}">
      <span class="cs-figure__n">${value}</span>
      <span class="cs-figure__label">${label}</span>
    </span>
  `;
}

function renderRow(row: StateRollup, calendar: Map<string, CalendarDay>, days: string[]) {
  const stale = row.oldest_days >= STALE_DAYS ? "cs-figure--alert" : "";
  return html`
    <div class="cs-row">
      <span class="cs-row__state">${row.state}</span>
      ${renderFigure(row.to_review, "to review", stale, queueTitle(row))}
      <span class="cs-cal">
        ${days.map((date) => renderDay(calendar.get(dayKey(row.state, date)), date, row.state))}
      </span>
      ${renderFigure(row.published, "published")}
      ${renderFigure(row.dismissed, "dismissed", row.dismissed ? "cs-figure--alert" : "")}
      ${renderFigure(row.roster_edits, "roster edits")}
    </div>
  `;
}

function renderLedger(rows: StateRollup[]) {
  const sum = (pick: (r: StateRollup) => number) => rows.reduce((n, r) => n + pick(r), 0);
  const figures = [
    { n: sum((r) => r.to_review), label: "to review" },
    { n: sum((r) => r.dismissed), label: "dismissed" },
    { n: sum((r) => r.published), label: "published" },
    { n: sum((r) => r.roster_edits), label: "roster edits" },
  ];
  return html`
    <div class="cs-ledger">
      ${figures.map(
        (f) => html`
          <span class="cs-ledger__figure">
            <span class="cs-ledger__n">${f.n}</span>
            <span class="cs-ledger__label">${f.label}</span>
          </span>
        `,
      )}
    </div>
  `;
}

type OpenBucket = { state: string; bucket: string };

function CivChangesetSummaries() {
  const { permissions } = useAuth();
  const [rows, setRows] = useState<StateRollup[] | null>(null);
  const [openBucket, setOpenBucket] = useState<OpenBucket | null>(null);
  // Bumped after a batch starts, so the rows refetch and the button reads its own effect.
  const [refresh, setRefresh] = useState(0);
  const [calendar, setCalendar] = useState<Map<string, CalendarDay>>(new Map());
  const [sortBy, setSortBy] = useState("queue");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchStateRollup(WINDOW_DAYS), fetchStateCalendar(WINDOW_DAYS)])
      .then(([rollup, days]: [StateRollup[], CalendarDay[]]) => {
        setRows(rollup);
        setCalendar(new Map(days.map((d) => [dayKey(d.state, d.day), d])));
      })
      .catch((err: Error) => setError(err.message));
  }, [refresh]);

  if (error) return html`<main class="cs-page"><p class="cs-empty">${error}</p></main>`;
  if (!rows) return html`<main class="cs-page"><p class="cs-empty">Loading…</p></main>`;

  const days = windowDays(WINDOW_DAYS);
  const ordered = [...rows].sort(SORTS[sortBy]);

  return html`
    <main class="cs-page">
      <div class="cs-head">
        <h1 class="cs-head__h1">Changesets</h1>
        ${renderLedger(rows)}
      </div>

      <hr class="cs-rule" />

      <div class="cs-chips">
        <span class="cs-chips__label">Sort by</span>
        ${CHIPS.map(
          (chip) => html`
            <button
              class="cs-chips__chip ${sortBy === chip.key ? "cs-chips__chip--active" : ""}"
              @click=${() => setSortBy(chip.key)}
            >
              ${chip.label}
            </button>
          `,
        )}
      </div>

      <div class="cs-legend">
        <span class="cs-legend__item"><strong>Calendar</strong></span>
        <span class="cs-legend__item">
          <span class="cs-legend__swatch cs-cal__seg--dismissed"></span> dismissed
        </span>
        <span class="cs-legend__item">
          <span class="cs-legend__swatch cs-cal__seg--review"></span> to review
        </span>
        <span class="cs-legend__item">
          <span class="cs-legend__swatch cs-cal__seg--published"></span> published
        </span>
        <span class="cs-legend__item">band size is that day's share</span>
        <span class="cs-legend__item">
          <span class="cs-legend__swatch cs-cal__cell--idle"></span> nothing ran
        </span>
      </div>

      ${renderScale(days)}
      <div>${ordered.map((row) => renderRow(row, calendar, days))}</div>

      <h2 class="cs-sections__h2">By state</h2>
      <div
        class="cs-sections"
        @open-bucket=${(e: CustomEvent) => setOpenBucket(e.detail as OpenBucket)}
        @scrape-started=${() => setRefresh((n: number) => n + 1)}
      >
        ${ordered.map(
          (row) => html`<civ-state-section
            .row=${row}
            .windowDays=${WINDOW_DAYS}
            .canScrape=${!!permissions.can_scrape}
          ></civ-state-section>`,
        )}
      </div>

      ${openBucket
        ? html`<civ-bucket-modal
            .state=${openBucket.state}
            .bucket=${openBucket.bucket}
            .windowDays=${WINDOW_DAYS}
            @close-bucket=${() => setOpenBucket(null)}
          ></civ-bucket-modal>`
        : nothing}
    </main>
  `;
}

customElements.define(
  "civ-changeset-summaries",
  component(CivChangesetSummaries as any, { useShadowDOM: false }),
);
