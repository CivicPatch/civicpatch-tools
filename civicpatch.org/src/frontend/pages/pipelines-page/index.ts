// Cadence, budget, and the trigger to scrape a state right now — the one action this page
// carries. Moved off the changesets page along with the batch-scrape permission itself: both
// are admin-only now, so neither belongs on the page any signed-in user reads.

import { component, useEffect, useState } from "haunted";
import { html, nothing } from "lit-html";
import "./pipelines-page.css";
import { fetchJurisdictionStates, fetchStateScrapeSettings, startStateScrape } from "../../api.js";
import "../../components/confirm-modal/confirm-modal.ts";
import "./scrape-settings-modal.ts";
import {
  describeAnchor,
  describeBudget,
  describeCadence,
  describeNextRun,
  type StateScrapePanel,
} from "./scrape-settings.js";

// Four places under a dollar, matching `formatUsd` in spend-page/spend.ts — a per-run cap of
// a fraction of a cent should not read as "$0.00".
import { formatUsd } from "../spend-page/spend.js";

const COLS = [
  { key: "cadence", label: "cadence" },
  { key: "next-run", label: "next run" },
  { key: "per-run", label: "per run" },
  { key: "month", label: "this month" },
  { key: "due", label: "due" },
] as const;

// One panel per state, in parallel — admin-only and infrequent, so N small requests cost less
// than the batched query and its own cache invalidation would.
async function fetchAllPanels(): Promise<StateScrapePanel[]> {
  const states: { code: string }[] = await fetchJurisdictionStates();
  const panels = await Promise.all(states.map((s) => fetchStateScrapeSettings(s.code)));
  return panels.sort((a: StateScrapePanel, b: StateScrapePanel) => a.state.localeCompare(b.state));
}

function renderHead() {
  return html`
    <div class="pipelines-page__row pipelines-page__row--head">
      <span class="pipelines-page__row-state">state</span>
      ${COLS.map(
        (col) =>
          html`<span class="pipelines-page__row-fig pipelines-page__row-fig--${col.key}"
            >${col.label}</span
          >`,
      )}
      <span></span>
      <span></span>
    </div>
  `;
}

function renderRow(
  panel: StateScrapePanel,
  onEdit: (state: string) => void,
  onScrapeClick: (state: string) => void,
  starting: string | null,
  scrapeError: string | null,
) {
  const overBudget = panel.cap_reached !== null;
  const anchor = describeAnchor(panel);
  return html`
    <div class="pipelines-page__row">
      <span class="pipelines-page__row-state">${panel.state}</span>
      <span class="pipelines-page__row-fig pipelines-page__row-fig--cadence">
        ${describeCadence(panel)}${anchor ? html`, ${anchor}` : nothing}
      </span>
      <span class="pipelines-page__row-fig pipelines-page__row-fig--next-run">
        ${describeNextRun(panel.next_run_at, new Date())}
      </span>
      <span class="pipelines-page__row-fig pipelines-page__row-fig--per-run">
        ${panel.pipeline_run_cap_usd ? formatUsd(panel.pipeline_run_cap_usd) : "no cap"}
      </span>
      <span
        class="pipelines-page__row-fig pipelines-page__row-fig--month
          ${overBudget ? "pipelines-page__row-fig--alert" : ""}"
      >
        ${describeBudget(panel.spent_this_month_usd, panel.monthly_cap_usd)}
        ${panel.cost_cap_hits_this_month
          ? html`<span class="pipelines-page__row-alert"
              >${panel.cost_cap_hits_this_month} hit the cap</span
            >`
          : nothing}
      </span>
      <span class="pipelines-page__row-fig pipelines-page__row-fig--due">
        ${panel.candidates_due ? `${panel.candidates_due} due` : "—"}
      </span>
      <button class="pipelines-page__edit" @click=${() => onEdit(panel.state)}>edit</button>
      <span class="pipelines-page__scrape">
        <button
          class="btn btn-sm pipelines-page__scrape-btn"
          ?disabled=${starting === panel.state}
          @click=${() => onScrapeClick(panel.state)}
        >
          ${starting === panel.state ? "Starting…" : "Scrape now"}
        </button>
        ${scrapeError ? html`<span class="pipelines-page__scrape-error">${scrapeError}</span>` : nothing}
      </span>
    </div>
  `;
}

function PipelinesPage() {
  const [panels, setPanels] = useState<StateScrapePanel[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingState, setEditingState] = useState<string | null>(null);
  const [confirmingState, setConfirmingState] = useState<string | null>(null);
  const [starting, setStarting] = useState<string | null>(null);
  const [scrapeErrors, setScrapeErrors] = useState<Record<string, string>>({});

  const load = () => {
    fetchAllPanels()
      .then(setPanels)
      .catch((err: Error) => setError(err.message));
  };

  useEffect(load, []);

  const editingPanel = panels?.find((p) => p.state === editingState) ?? null;

  // Confirmed, not fired on click: a batch spends real money and cannot be recalled.
  const confirmScrape = () => {
    const state = confirmingState as string;
    setConfirmingState(null);
    setStarting(state);
    setScrapeErrors((prev) => ({ ...prev, [state]: "" }));
    startStateScrape(state)
      .catch((err: Error) => setScrapeErrors((prev) => ({ ...prev, [state]: err.message })))
      .finally(() => setStarting(null));
  };

  if (error) return html`<main class="pipelines-page page-content"><p class="pipelines-page__empty">${error}</p></main>`;
  if (!panels) return html`<main class="pipelines-page page-content"><p class="pipelines-page__empty">Loading…</p></main>`;

  return html`
    <main class="pipelines-page page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Pipelines</h1>
      </div>

      <div class="pipelines-page__list">
        ${renderHead()}
        ${panels.map((panel) =>
          renderRow(panel, setEditingState, setConfirmingState, starting, scrapeErrors[panel.state] || null),
        )}
      </div>

      ${editingPanel
        ? html`<civ-scrape-settings-modal
            .panel=${editingPanel}
            @settings-saved=${() => {
              setEditingState(null);
              load();
            }}
            @cancel=${() => setEditingState(null)}
          ></civ-scrape-settings-modal>`
        : nothing}

      ${confirmingState
        ? html`<civ-confirm-modal
            .title=${`Scrape ${confirmingState.toUpperCase()}?`}
            .message=${`Scrapes every jurisdiction in ${confirmingState.toUpperCase()} that is due — however many that is. They cost money to run and cannot be stopped once started.`}
            .confirmLabel=${"Start scraping"}
            .variant=${"danger"}
            @confirm=${confirmScrape}
            @cancel=${() => setConfirmingState(null)}
          ></civ-confirm-modal>`
        : nothing}
    </main>
  `;
}

customElements.define("pipelines-page", component(PipelinesPage as any, { useShadowDOM: false }));
