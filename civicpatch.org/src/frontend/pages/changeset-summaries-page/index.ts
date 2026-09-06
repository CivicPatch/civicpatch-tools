// Changeset activity across every state, for maintainers and up: what is waiting on a reviewer
// and how long it has waited, what ran each day, and what came of it.
//
// Not a scrape page, and deliberately not named one — `sheet_import` is 76% of changesets and
// `scrape` 24%, so labelling these figures "scrapes" would misreport three quarters of them.

import { component, useEffect, useState } from "haunted";
import { html, nothing } from "lit-html";
import "./changeset-summaries.css";
import { fetchStateCalendar, fetchStateRollup, fetchStateSpend } from "../../api.js";
import { useAuth } from "../../hooks/useAuth.js";
import {
  dayKey,
  renderDay,
  renderScale,
  windowDays,
  type CalendarDay,
} from "./calendar.js";
import {
  costPerScrapeOf,
  formatUsd,
  spendChangeOf,
  spendOf,
  type StateSpend,
} from "./spend.js";
import { hasPickedEverything, isShown, toggle } from "./selection.js";
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

// Every comparator takes the spend map, whether it reads it or not: one registry that all
// sorts share beats two that have to be kept in step.
type Sort = (a: StateRollup, b: StateRollup, spend: SpendByState) => number;
type SpendByState = Map<string, StateSpend> | null;

const by = (pick: (spend: StateSpend | undefined) => number): Sort =>
  (a, b, spend) => pick(spend?.get(b.state)) - pick(spend?.get(a.state));

const SORTS: Record<string, Sort> = {
  queue: (a, b) => b.to_review - a.to_review,
  oldest: (a, b) => b.oldest_days - a.oldest_days,
  dismissed: (a, b) => b.dismissed - a.dismissed,
  spend: by(spendOf),
  cost: by(costPerScrapeOf),
  trend: by(spendChangeOf),
  name: (a, b) => a.state.localeCompare(b.state),
};

const CHIPS = [
  { key: "queue", label: "To review" },
  { key: "oldest", label: "Longest waiting" },
  { key: "dismissed", label: "Dismissed" },
  { key: "name", label: "State" },
];

// Only offered when spend is on screen — a chip that sorts by a column you cannot see would
// reorder the table for no visible reason.
const SPEND_CHIPS = [
  { key: "spend", label: "Spend" },
  { key: "cost", label: "Cost per run" },
  { key: "trend", label: "Rising spend" },
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

// `rows` is the selection, not the fleet — the ledger answers for what is on screen.
function renderLedger(rows: StateRollup[], spend: SpendByState) {
  const sum = (pick: (r: StateRollup) => number) => rows.reduce((n, r) => n + pick(r), 0);
  const figures = [
    { n: sum((r) => r.to_review), label: "to review" },
    { n: sum((r) => r.dismissed), label: "dismissed" },
    { n: sum((r) => r.published), label: "published" },
    { n: sum((r) => r.roster_edits), label: "roster edits" },
  ];
  // A fleet total is a real total even when a member spent nothing, so summing over the
  // nothings is right here — unlike the per-state figure, where 0 would be a claim.
  const spendTotal = spend
    ? rows.reduce((n, row) => n + spendOf(spend.get(row.state)), 0)
    : null;
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
      ${spendTotal === null
        ? nothing
        : html`
            <span class="cs-ledger__figure">
              <span class="cs-ledger__n">${formatUsd(String(spendTotal))}</span>
              <span class="cs-ledger__label">spend, 30d</span>
            </span>
          `}
    </div>
  `;
}

// Scoped to the selection, like the ledger: it answers for what is on screen.
//
// Jurisdictions only. Organizations are punted — every jurisdiction has exactly one today, so a
// second count would print the same number twice. Worth adding when a place actually holds a
// council and a school board.
//
// Absent rather than empty when nothing runs: a banner that says "0 scraping" is a banner
// asking to be read every time, to learn nothing.
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

type OpenBucket = { state: string; bucket: string };

function CivChangesetSummaries() {
  const { permissions } = useAuth();
  const [rows, setRows] = useState<StateRollup[] | null>(null);
  const [openBucket, setOpenBucket] = useState<OpenBucket | null>(null);
  // Bumped after a batch starts, so the rows refetch and the button reads its own effect.
  const [refresh, setRefresh] = useState(0);
  const [calendar, setCalendar] = useState<Map<string, CalendarDay>>(new Map());
  // `null` means not shown at all, which is not the same as an empty map (permitted, but
  // nothing spent). The column only exists for the first.
  const [spend, setSpend] = useState<Map<string, StateSpend> | null>(null);
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
  }, [refresh]);

  // Its own effect, and its own failure: spend is a second request that 403s for most users,
  // so a refusal here must not blank the page the way the rollup's would.
  useEffect(() => {
    if (!permissions.can_edit_spend) return;
    fetchStateSpend(WINDOW_DAYS)
      .then((rows: StateSpend[]) => setSpend(new Map(rows.map((r) => [r.state, r]))))
      .catch(() => setSpend(null));
  }, [refresh, permissions.can_edit_spend]);

  if (error) return html`<main class="cs-page"><p class="cs-empty">${error}</p></main>`;
  if (!rows) return html`<main class="cs-page"><p class="cs-empty">Loading…</p></main>`;

  const days = windowDays(WINDOW_DAYS);
  const ordered = [...rows].sort((a, b) => SORTS[sortBy](a, b, spend));
  const chips = spend ? [...CHIPS, ...SPEND_CHIPS] : CHIPS;
  const shown = ordered.filter((row) => isShown(picked, row.state));

  return html`
    <main class="cs-page">
      <div class="cs-head">
        <h1 class="cs-head__h1">Changesets</h1>
        ${renderLedger(shown, spend)}
      </div>

      <hr class="cs-rule" />

      <div class="cs-chips">
        <span class="cs-chips__label">Sort by</span>
        ${chips.map(
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

      <h2 class="cs-sections__h2">By state</h2>
      <div
        class="cs-sections"
        @open-bucket=${(e: CustomEvent) => setOpenBucket(e.detail as OpenBucket)}
        @scrape-started=${() => setRefresh((n: number) => n + 1)}
      >
        ${shown.map(
          (row) => html`<civ-state-section
            .row=${row}
            .windowDays=${WINDOW_DAYS}
            .canScrape=${!!permissions.can_scrape}
            .spend=${spend ? (spend.get(row.state) ?? null) : null}
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
