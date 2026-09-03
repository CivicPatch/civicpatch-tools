// One state's section: the figures as badges, and the localities behind each one.
//
// Buckets load on first open, not with the page. Three requests per state across fifteen states
// would be 45 on load, for lists most readers never open.

import { component, useState } from "haunted";
import "./state-section.css";
import "../../components/status-badge.js";
import { html, nothing } from "lit-html";
import { fetchStateBucket, startStateScrape } from "../../api.js";
import "../../components/confirm-modal/confirm-modal.ts";
import { hostDispatch } from "../../utils/host-dispatch.js";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";
import {
  BUCKET_FAILED,
  BUCKET_OK,
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
    confirmed: number;
    rejected: number;
    errored: number;
    roster_edits: number;
  };
  windowDays: number;
  canScrape: boolean;
};

const BUCKETS = [
  { key: BUCKET_REVIEW, count: (r: any) => r.to_review },
  { key: BUCKET_FAILED, count: (r: any) => r.rejected + r.errored },
  { key: BUCKET_OK, count: (r: any) => r.confirmed },
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

  const badge = (n: number, text: string, tone: string) =>
    n
      ? html`<civ-status-badge
          label=${`${n} ${text}`}
          bg=${TONES[tone].bg}
          color=${TONES[tone].color}
        ></civ-status-badge>`
      : nothing;

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
        <span class="cs-scrape__note">No schedule</span>
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

  const failed = row.rejected + row.errored;
  const nothingRan = !row.to_review && !failed && !row.confirmed;

  return html`
    <details class="cs-section" @toggle=${handleToggle}>
      <summary class="cs-section__summary">
        <span class="cs-section__state">${row.state}</span>
        <span class="cs-section__badges">
          ${nothingRan
            ? html`<civ-status-badge
                label="Nothing ran"
                bg=${TONES.quiet.bg}
                color=${TONES.quiet.color}
              ></civ-status-badge>`
            : html`
                ${badge(row.to_review, "to review", "review")}
                ${badge(failed, "failed", "alert")}
                ${badge(row.confirmed, "ok", "ok")}
                ${badge(row.roster_edits, "roster edits", "quiet")}
              `}
        </span>
      </summary>
      <div class="cs-section__body">
        ${host.canScrape ? renderScrapeControl() : nothing}
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
