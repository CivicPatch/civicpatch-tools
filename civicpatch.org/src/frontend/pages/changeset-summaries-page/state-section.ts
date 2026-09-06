// One state's section: the figures as badges, and the localities behind each one.
//
// Buckets load on first open, not with the page. Three requests per state across fifteen states
// would be 45 on load, for lists most readers never open.

import { component, useState } from "haunted";
import "./state-section.css";
import "../../components/status-badge.js";
import { html, nothing } from "lit-html";
import { fetchStateBucket, fetchStateScrapeSettings, startStateScrape } from "../../api.js";
import "../../components/confirm-modal/confirm-modal.ts";
import "./scrape-settings-modal.ts";
import { hostDispatch } from "../../utils/host-dispatch.js";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";
import { formatChange, formatUsd, spendChangeOf, type StateSpend } from "./spend.js";
import {
  describeBudget,
  describeCadence,
  describeNextRun,
  type StateScrapePanel,
} from "./scrape-settings.js";
import {
  BUCKET_DISMISSED,
  BUCKET_FAILED_RUNS,
  BUCKET_PUBLISHED,
  BUCKET_REVIEW,
  BUCKET_LABEL,
  type BucketPage,
  type BucketRow,
} from "./buckets.js";

// Enough to show a section is not empty; the rest is the modal's job.
const PREVIEW = 8;

export const OPEN_BUCKET_EVENT = "open-bucket";
export const SCRAPE_STARTED_EVENT = "scrape-started";

type StateSectionHost = HTMLElement & {
  row: {
    state: string;
    running: number;
    to_review: number;
    published: number;
    dismissed: number;
    roster_edits: number;
    failed_runs: number;
  };
  windowDays: number;
  canScrape: boolean;
  canEditSettings: boolean;
  // Null for two reasons that render alike: not a maintainer, or the state spent nothing.
  // Neither is $0.00, which would claim it scraped for free.
  spend: StateSpend | null;
};

const BUCKETS = [
  { key: BUCKET_REVIEW, count: (r: any) => r.to_review },
  { key: BUCKET_DISMISSED, count: (r: any) => r.dismissed },
  { key: BUCKET_PUBLISHED, count: (r: any) => r.published },
  // Not a proposal like the three above — an attempt that made none. It opens the same way so
  // the count stops being a dead end: which locality, and why it ended.
  { key: BUCKET_FAILED_RUNS, count: (r: any) => r.failed_runs },
];

// The app's own badge, driven by the pico tone pairs rather than a private set of pills.
const TONES: Record<string, { bg: string; color: string }> = {
  review: { bg: "rgba(var(--tone-yellow), 0.2)", color: "rgb(var(--tone-yellow))" },
  alert: { bg: "var(--pico-del-background)", color: "var(--pico-del-color)" },
  ok: { bg: "var(--pico-ins-background)", color: "var(--pico-ins-color)" },
  quiet: { bg: "var(--pico-muted-background)", color: "var(--civ-text-muted)" },
};

const label = (row: BucketRow) => row.name ?? row.jurisdiction_ocdid;

// `days_waiting` and `failure_reason` arrive structured, so the phrasing lives here.
function noteFor(row: BucketRow) {
  if (row.days_waiting != null) {
    return html`<span class="cs-bucket__note"
      >${row.days_waiting} day${row.days_waiting === 1 ? "" : "s"}</span
    >`;
  }
  if (row.failure_reason) return html`<span class="cs-bucket__note">${row.failure_reason}</span>`;
  return nothing;
}

function CivStateSection(host: StateSectionHost) {
  const { row, windowDays } = host;
  const [pages, setPages] = useState<Record<string, BucketPage>>({});
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [starting, setStarting] = useState(false);
  const [scrapeError, setScrapeError] = useState<string | null>(null);
  const [settings, setSettings] = useState<StateScrapePanel | null>(null);
  const [editing, setEditing] = useState(false);

  const load = () => {
    if (loading || Object.keys(pages).length) return;
    setLoading(true);
    Promise.all(
      BUCKETS.filter((b) => b.count(row)).map((b) =>
        fetchStateBucket(row.state, b.key, PREVIEW, 0, windowDays).then(
          (page: BucketPage) => [b.key, page] as const,
        ),
      ),
    )
      .then((entries) => setPages(Object.fromEntries(entries)))
      .catch(() => setPages({}))
      .finally(() => setLoading(false));
    if (host.canEditSettings) loadSettings();
  };

  // `toggle` rather than a click handler on the summary: it fires for keyboard opens too.
  const handleToggle = (e: Event) => {
    if ((e.target as HTMLDetailsElement).open) load();
  };

  // Confirmed, not fired on click: a batch spends real money and cannot be recalled.
  const confirmScrape = () => {
    setConfirming(false);
    setStarting(true);
    setScrapeError(null);
    startStateScrape(row.state)
      .then(() => hostDispatch(host, SCRAPE_STARTED_EVENT, { state: row.state }))
      .catch((err: Error) => setScrapeError(err.message))
      .finally(() => setStarting(false));
  };

  const openBucket = (bucket: string) =>
    hostDispatch(host, OPEN_BUCKET_EVENT, { state: row.state, bucket });

  function renderBucket(bucket: (typeof BUCKETS)[number]) {
    const total = bucket.count(row);
    if (!total) return nothing;
    const page = pages[bucket.key];
    // The bucket's own total counts localities; the badge counts changesets. They differ, so
    // "+N more" is computed from the bucket's number, never the row's.
    const hidden = page ? page.total - page.rows.length : 0;
    return html`
      <div class="cs-bucket">
        <p class="cs-bucket__head">
          ${BUCKET_LABEL[bucket.key]}
          <span class="cs-bucket__n">${page ? page.total : total}</span>
        </p>
        <div class="cs-bucket__list">
          ${page
            ? page.rows.map(
                (item) => html`<a class="cs-bucket__item" href="/${jurisdictionOcdidToPath(item.jurisdiction_path)}">
                  <span>${label(item)}</span>
                  ${noteFor(item)}
                </a>`,
              )
            : html`<span class="cs-empty">Loading…</span>`}
        </div>
        ${hidden > 0
          ? html`<button class="cs-bucket__more" @click=${() => openBucket(bucket.key)}>
              +${hidden} more
            </button>`
          : nothing}
      </div>
    `;
  }

  const money = (label: string) =>
    html`<civ-status-badge
      label=${label}
      bg=${TONES.quiet.bg}
      color=${TONES.quiet.color}
    ></civ-status-badge>`;

  // In the header rather than the row: a currency figure beside thirty calendar cells and
  // three counts is what broke that line, and this is where a state's own numbers belong.
  //
  // All three, because each is what one of the spend sorts ranks by — a sort whose figure is
  // nowhere on screen reorders the page for no visible reason.
  function renderSpend(spend: StateSpend | null) {
    if (!spend) return nothing;
    const change = spendChangeOf(spend);
    return html`
      ${spend.spend_usd
        ? money(`${formatUsd(spend.spend_usd)} spent, ${host.windowDays}d`)
        : nothing}
      ${spend.cost_per_scrape_usd
        ? money(`${formatUsd(spend.cost_per_scrape_usd)} per run`)
        : nothing}
      ${spend.prior_spend_usd
        ? money(`${formatChange(change)} vs prior ${host.windowDays}d`)
        : nothing}
    `;
  }

  const badge = (n: number, text: string, tone: string) =>
    n
      ? html`<civ-status-badge
          label=${`${n} ${text}`}
          bg=${TONES[tone].bg}
          color=${TONES[tone].color}
        ></civ-status-badge>`
      : nothing;

  // Attempts, kept apart from the badges above, which are all proposals. A run is not a
  // proposal: it mints one only if it reaches ingest, so a failed run is in none of those
  // counts. Body-only on purpose — this is for seeing activity and debugging, and the
  // collapsed row is about what needs a reviewer.
  function renderRuns() {
    if (!row.running && !row.failed_runs) return nothing;
    return html`
      <div class="cs-runs">
        <span class="cs-runs__label">Pipeline runs</span>
        ${row.running ? html`<span class="cs-runs__fig">${row.running} running</span>` : nothing}
        ${row.failed_runs
          ? html`<button
              type="button"
              class="cs-runs__fig cs-runs__fig--quiet cs-runs__fig--open"
              @click=${() => openBucket(BUCKET_FAILED_RUNS)}
            >
              ${row.failed_runs} failed in ${host.windowDays} days
            </button>`
          : nothing}
      </div>
    `;
  }

  const loadSettings = () =>
    fetchStateScrapeSettings(row.state)
      .then(setSettings)
      .catch(() => setSettings(null));

  // Absent until the section is opened, so this renders nothing rather than a skeleton.
  function renderSettings() {
    if (!settings) return nothing;
    const overBudget = settings.cap_reached !== null;
    return html`
      <span class="cs-settings">
        <span class="cs-settings__fig">${describeCadence(settings)}</span>
        <span class="cs-settings__sep">|</span>
        <span class="cs-settings__fig">${describeNextRun(settings.next_run_at, new Date())}</span>
        <span class="cs-settings__sep">|</span>
        <span class="cs-settings__fig ${overBudget ? "cs-settings__fig--alert" : ""}">
          ${describeBudget(settings.spent_this_month_usd, settings.monthly_cap_usd)}
          this month
        </span>
        ${settings.candidates_due
          ? html`<span class="cs-settings__sep">|</span>
              <span class="cs-settings__fig">${settings.candidates_due} due</span>`
          : nothing}
        ${settings.cost_cap_hits_this_month
          ? html`<span class="cs-settings__sep">|</span>
              <span class="cs-settings__fig cs-settings__fig--alert"
                >${settings.cost_cap_hits_this_month} hit the run cap</span
              >`
          : nothing}
        <button class="cs-settings__edit" @click=${() => setEditing(true)}>edit</button>
      </span>
      ${editing
        ? html`<civ-scrape-settings-modal
            .panel=${settings}
            
            @settings-saved=${() => {
              setEditing(false);
              loadSettings();
            }}
            @cancel=${() => setEditing(false)}
          ></civ-scrape-settings-modal>`
        : nothing}
    `;
  }

  // Disabled while this state has a run going: a second batch on top of a live one is the
  // mistake the count exists to prevent.
  function renderScrapeControl() {
    const busy = row.running > 0;
    return html`
      <div class="cs-scrape">
        <button
          class="btn btn-sm cs-scrape__btn"
          ?disabled=${busy || starting}
          @click=${() => setConfirming(true)}
        >
          ${starting ? "Starting…" : "Scrape this state"}
        </button>
        ${busy
          ? html`<span class="cs-scrape__busy">${row.running} already running</span>`
          : nothing}
        ${scrapeError ? html`<span class="cs-scrape__error">${scrapeError}</span>` : nothing}
        ${renderSettings()}
      </div>
      ${confirming
        ? html`<civ-confirm-modal
            .title=${`Scrape ${row.state.toUpperCase()}?`}
            .message=${`Scrapes every jurisdiction in ${row.state.toUpperCase()} that is due — however many that is. They cost money to run and cannot be stopped once started.`}
            .confirmLabel=${"Start scraping"}
            .variant=${"danger"}
            @confirm=${confirmScrape}
            @cancel=${() => setConfirming(false)}
          ></civ-confirm-modal>`
        : nothing}
    `;
  }

  const nothingRan = !row.to_review && !row.dismissed && !row.published;

  return html`
    <details class="cs-section" @toggle=${handleToggle}>
      <summary class="cs-section__summary">
        <span class="cs-section__state">${row.state}</span>
        <span class="cs-section__badges">
          ${renderSpend(host.spend)}
          ${nothingRan
            ? html`<civ-status-badge
                label="Nothing ran"
                bg=${TONES.quiet.bg}
                color=${TONES.quiet.color}
              ></civ-status-badge>`
            : html`
                ${badge(row.to_review, "to review", "review")}
                ${badge(row.dismissed, "dismissed", "alert")}
                ${badge(row.published, "published", "ok")}
                ${badge(row.roster_edits, "roster edits", "quiet")}
              `}
        </span>
      </summary>
      <div class="cs-section__body">
        ${host.canScrape ? renderScrapeControl() : nothing} ${renderRuns()}
        ${nothingRan
          ? html`<p class="cs-empty">Nothing ran in this window.</p>`
          : BUCKETS.map(renderBucket)}
      </div>
    </details>
  `;
}

customElements.define(
  "civ-state-section",
  component(CivStateSection as any, { useShadowDOM: false }),
);
