// What scraping costs, per state — the global cap, and the state-by-state ledger behind it.
//
// Split out of the changesets page: money is an admin concern (`can_edit_spend` is
// ADMINS-only), unlike changesets, which any signed-in user reads.

import { component, useEffect, useState } from "haunted";
import { html, nothing } from "lit-html";
import "./spend-page.css";
import { fetchGlobalScrapeSettings, fetchStateSpend } from "../../api.js";
import { useAuth } from "../../hooks/useAuth.js";
import {
  costPerScrapeOf,
  formatChange,
  formatUsd,
  spendChangeOf,
  spendOf,
  type StateSpend,
} from "./spend.js";
import {
  describeBudget,
  describeStateCaps,
  type GlobalScrapePanel,
} from "../pipelines-page/scrape-settings.js";
import "./global-budget-modal.ts";
import { SectionNav, adminSection } from "../../components/section-nav/index.js";

const WINDOW_DAYS = 30;

type Sort = (a: StateSpend, b: StateSpend) => number;

const SORTS: Record<string, Sort> = {
  spend: (a, b) => spendOf(b) - spendOf(a),
  cost: (a, b) => costPerScrapeOf(b) - costPerScrapeOf(a),
  trend: (a, b) => spendChangeOf(b) - spendChangeOf(a),
  name: (a, b) => a.state.localeCompare(b.state),
};

const CHIPS = [
  { key: "spend", label: "Spend" },
  { key: "cost", label: "Cost per run" },
  { key: "trend", label: "Rising spend" },
  { key: "name", label: "State" },
];

function renderLedger(rows: StateSpend[]) {
  const total = rows.reduce((n, r) => n + spendOf(r), 0);
  return html`
    <div class="spend-page__ledger">
      <span class="spend-page__ledger-figure">
        <span class="spend-page__ledger-n">${formatUsd(String(total))}</span>
        <span class="spend-page__ledger-label">spend, ${WINDOW_DAYS}d</span>
      </span>
    </div>
  `;
}

// Jurisdictions only, absent rather than empty when nothing runs: a banner reading "$0" is a
// banner asking to be read every time, to learn nothing.
function renderBudget(panel: GlobalScrapePanel, canEdit: boolean, onEdit: () => void) {
  return html`
    <div class="spend-page__budget">
      <span class="spend-page__budget-label">All states</span>
      <span class="spend-page__budget-fig">
        ${describeBudget(panel.spent_this_month_usd, panel.monthly_cap_usd)} this month
      </span>
      <span class="spend-page__budget-fig spend-page__budget-fig--quiet">${describeStateCaps(panel)}</span>
      ${canEdit
        ? html`<button class="spend-page__budget-edit" @click=${onEdit}>edit</button>`
        : nothing}
    </div>
  `;
}

function renderFigure(value: string, label: string) {
  return html`
    <span class="spend-page__row-fig">
      <span class="spend-page__row-n">${value}</span>
      <span class="spend-page__row-label">${label}</span>
    </span>
  `;
}

function renderRow(row: StateSpend) {
  return html`
    <div class="spend-page__row">
      <span class="spend-page__row-state">${row.state}</span>
      ${renderFigure(row.spend_usd ? formatUsd(row.spend_usd) : "—", `spent, ${WINDOW_DAYS}d`)}
      ${renderFigure(row.cost_per_scrape_usd ? formatUsd(row.cost_per_scrape_usd) : "—", "per run")}
      ${renderFigure(
        row.prior_spend_usd ? formatChange(spendChangeOf(row)) : "—",
        `vs prior ${WINDOW_DAYS}d`,
      )}
    </div>
  `;
}

function SpendPage() {
  const { permissions } = useAuth();
  const [rows, setRows] = useState<StateSpend[] | null>(null);
  const [budget, setBudget] = useState<GlobalScrapePanel | null>(null);
  const [editingBudget, setEditingBudget] = useState(false);
  const [sortBy, setSortBy] = useState("spend");
  const [error, setError] = useState<string | null>(null);
  // Bumped after the budget saves, so the banner refetches and reads its own edit.
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    fetchStateSpend(WINDOW_DAYS)
      .then(setRows)
      .catch((err: Error) => setError(err.message));
  }, [refresh]);

  useEffect(() => {
    fetchGlobalScrapeSettings()
      .then(setBudget)
      .catch(() => setBudget(null));
  }, [refresh]);

  if (error) {
    return html`<main class="spend-page page-content"><p class="spend-page__empty">${error}</p></main>`;
  }
  if (!rows) {
    return html`<main class="spend-page page-content"><p class="spend-page__empty">Loading…</p></main>`;
  }

  const ordered = [...rows].sort(SORTS[sortBy]);

  return html`
    <main class="spend-page page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Spend</h1>
        ${renderLedger(rows)}
      </div>

      <div class="sectioned">
      ${SectionNav("admin", adminSection(permissions), "/spend")}
      <div class="secbody">

      ${budget
        ? renderBudget(budget, !!permissions.can_write_global_config, () => setEditingBudget(true))
        : nothing}
      ${editingBudget && budget
        ? html`<civ-global-budget-modal
            .panel=${budget}
            @settings-saved=${() => {
              setEditingBudget(false);
              setRefresh((n: number) => n + 1);
            }}
            @cancel=${() => setEditingBudget(false)}
          ></civ-global-budget-modal>`
        : nothing}

      <div class="spend-page__chips">
        <span class="spend-page__chips-label">Sort by</span>
        ${CHIPS.map(
          (chip) => html`
            <button
              class="spend-page__chip ${sortBy === chip.key ? "spend-page__chip--active" : ""}"
              @click=${() => setSortBy(chip.key)}
            >
              ${chip.label}
            </button>
          `,
        )}
      </div>

      ${ordered.length
        ? html`<div class="spend-page__list">${ordered.map(renderRow)}</div>`
        : html`<p class="spend-page__empty">No spend recorded.</p>`}
      </div>
      </div>
    </main>
  `;
}

customElements.define("spend-page", component(SpendPage as any, { useShadowDOM: false }));
