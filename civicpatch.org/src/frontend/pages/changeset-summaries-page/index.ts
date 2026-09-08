// Changeset activity across every state, for maintainers and up: what is waiting on a reviewer
// and how long it has waited, what ran each day, and what came of it.
//
// Not a scrape page, and deliberately not named one — `sheet_import` is 76% of changesets and
// `scrape` 24%, so labelling these figures "scrapes" would misreport three quarters of them.

import { component, useEffect, useState } from "haunted";
import { html, nothing } from "lit-html";
import "./changeset-summaries.css";
import { fetchStateCalendar, fetchStateRollup } from "../../api.js";
import {
  dayKey,
  renderDay,
  renderScale,
  windowDays,
  type CalendarDay,
} from "./calendar.js";
import { SectionNav, ACTIVITY_SECTION } from "../../components/section-nav/index.js";
import { hasPickedEverything, isShown, toggle } from "./selection.js";

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

const LIFECYCLE = [
  { key: "published", label: "published", tone: "ok" },
  { key: "to_review", label: "to review", tone: "open" },
  { key: "dismissed", label: "dismissed", tone: "bad" },
] as const;

// Summed over the states in view, so filtering the list re-reads the outcome mix.
function renderLifecycle(shown: StateRollup[]) {
  const totals = LIFECYCLE.map((band) => ({
    ...band,
    n: shown.reduce((sum, row) => sum + (row[band.key] ?? 0), 0),
  }));
  const total = totals.reduce((sum, band) => sum + band.n, 0);
  if (!total) return nothing;

  return html`
    <section class="panel cs-flow">
      <div class="panel__cap">
        <b>lifecycle</b>
        <span class="panel__cap-right">${total} changesets</span>
      </div>
      ${totals.map(
        (band) => html`
          <div class="cs-flow__row">
            <span class="cs-flow__label">${band.label}</span>
            <span class="cs-flow__bar"
              ><i
                class="cs-flow__fill cs-flow__fill--${band.tone}"
                style="width:${((band.n / total) * 100).toFixed(1)}%"
              ></i
            ></span>
            <span class="cs-flow__n">${band.n}</span>
          </div>
        `,
      )}
    </section>
  `;
}

type Sort = (a: StateRollup, b: StateRollup) => number;

const SORTS: Record<string, Sort> = {
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

// `rows` is the selection, not every state — the ledger answers for what is on screen.
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

function renderRunning(rows: StateRollup[]) {
  const live = rows.filter((row) => row.running);
  if (!live.length) return nothing;
  const total = live.reduce((n, row) => n + row.running, 0);
  return html`
    <div class="cs-running">
      <span>
        <span class="cs-running__n">${total}</span>
        jurisdiction${total === 1 ? "" : "s"} scraping now
      </span>
      <span class="cs-running__where">
        ${live.map((row) => `${row.state.toUpperCase()} ${row.running}`).join(", ")}
      </span>
    </div>
  `;
}

// Two actions, not a checkbox. A checkbox is a state control and would have to report
// none / some / all from two positions, so one of them would have to lie. What these can carry
// instead is whether there is anything left to do — greyed out means you are already there.
//
// **Fixed alphabetical order, never the active sort.** The sort reorders the data; it must not
// reorder this. A chip that moves under the cursor is a chip whose position cannot be learned,
// and at fifty states every sort change would reshuffle all fifty.
function renderCompare(
  rows: StateRollup[],
  picked: string[],
  setPicked: (next: string[]) => void,
) {
  const ordered = [...rows].sort((a, b) => a.state.localeCompare(b.state));
  return html`
    <div class="cs-chips cs-compare">
      <span class="cs-chips__label">Compare</span>
      <button
        class="cs-chips__chip cs-compare__action"
        ?disabled=${hasPickedEverything(picked, ordered.length)}
        @click=${() => setPicked(ordered.map((row) => row.state))}
      >
        all
      </button>
      <button
        class="cs-chips__chip cs-compare__action"
        ?disabled=${picked.length === 0}
        @click=${() => setPicked([])}
      >
        none
      </button>
      ${ordered.map(
        (row) => html`
          <button
            class="cs-chips__chip"
            aria-pressed=${picked.includes(row.state)}
            @click=${() => setPicked(toggle(picked, row.state))}
          >
            ${row.state}
          </button>
        `,
      )}
      <span class="cs-compare__note">
        ${picked.length ? `${picked.length} of ${ordered.length}` : ""}
      </span>
    </div>
  `;
}

function CivChangesetSummaries() {
  const [rows, setRows] = useState<StateRollup[] | null>(null);
  const [calendar, setCalendar] = useState<Map<string, CalendarDay>>(new Map());
  const [sortBy, setSortBy] = useState("queue");
  // Independent of `sortBy`, which is what makes a selection survive a sort change.
  const [picked, setPicked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchStateRollup(WINDOW_DAYS), fetchStateCalendar(WINDOW_DAYS)])
      .then(([rollup, days]: [StateRollup[], CalendarDay[]]) => {
        setRows(rollup);
        setCalendar(new Map(days.map((d) => [dayKey(d.state, d.day), d])));
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) return html`<main class="cs-page page-content"><p class="cs-empty">${error}</p></main>`;
  if (!rows) return html`<main class="cs-page page-content"><p class="cs-empty">Loading…</p></main>`;

  const days = windowDays(WINDOW_DAYS);
  const ordered = [...rows].sort((a, b) => SORTS[sortBy](a, b));
  const shown = ordered.filter((row) => isShown(picked, row.state));

  return html`
    <main class="cs-page page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Changesets</h1>
        <div class="page-focal__end">${renderLedger(shown)}</div>
      </div>

      <div class="sectioned">
      ${SectionNav("activity", ACTIVITY_SECTION, "/activity/changesets")}
      <div class="secbody">

      ${renderLifecycle(shown)}

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

      ${renderRunning(shown)}

      ${renderCompare(rows, picked, setPicked)}

      ${renderScale(days)}
      <div>${shown.map((row) => renderRow(row, calendar, days))}</div>
      </div>
      </div>
    </main>
  `;
}

customElements.define(
  "civ-changeset-summaries",
  component(CivChangesetSummaries as any, { useShadowDOM: false }),
);
