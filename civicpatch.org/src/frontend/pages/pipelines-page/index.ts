// Each pipeline's cadence and budget per state, and the trigger to run a state's pass now. Admin
// only: how often a pipeline runs is what it costs.

import { component, useEffect, useState } from "haunted";
import { html, nothing, type TemplateResult } from "lit-html";
import "./pipelines-page.css";
import {
  fetchActivePipelineRuns,
  fetchGlobalPipelineSettings,
  fetchJurisdictionStates,
  fetchPipelinePanel,
  startStatePass,
} from "../../api.js";
import "../../components/confirm-modal/confirm-modal.ts";
import "./pipeline-settings-modal.ts";
import "./global-budget-modal.ts";
import "./active-runs/index.js";
import { PIPELINE_KINDS, PIPELINE_LABELS, PipelineKind } from "../../schemas/pipeline-kinds.js";
import {
  describeAnchor,
  describeBudget,
  describeCadence,
  describeNextPass,
  describeNextRun,
  describePerRun,
  formatDuration,
  formatUsd,
  type GlobalPanel,
  type PassAverages,
  type PipelinePanel,
} from "./pipeline-settings.js";
import { useAuth } from "../../hooks/useAuth.js";
import { SectionNav, adminSection } from "../../components/section-nav/index.js";

const RUNS_PER_PAGE_CHOICES = [10, 25, 50];
const RUNS_POLL_MS = 5000;

function getIntParam(key: string, fallback: number, allowed: number[] | null = null): number {
  const val = parseInt(new URLSearchParams(window.location.search).get(key) ?? "", 10);
  if (isNaN(val) || val < 1) return fallback;
  if (allowed && !allowed.includes(val)) return fallback;
  return val;
}

function setRunsParamsInUrl(page: number, perPage: number): void {
  const params = new URLSearchParams(window.location.search);
  params.set("runs_page", String(page));
  params.set("runs_per_page", String(perPage));
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function getPipelineFromUrl(): PipelineKind {
  const val = new URLSearchParams(window.location.search).get("pipeline");
  return PIPELINE_KINDS.find((kind) => kind === val) ?? PipelineKind.PEOPLE;
}

function setPipelineInUrl(kind: PipelineKind): void {
  const params = new URLSearchParams(window.location.search);
  params.set("pipeline", kind);
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function getStateFromUrl(): string {
  const val = new URLSearchParams(window.location.search).get("state");
  return val ? val.toLowerCase() : "";
}

const COLS = [
  { key: "cadence", label: "cadence" },
  { key: "next-run", label: "next run" },
  { key: "per-run", label: "avg per run" },
  { key: "month", label: "this month" },
  { key: "due", label: "due" },
  { key: "est-cost", label: "est. cost" },
  { key: "wall-clock", label: "wall-clock" },
  { key: "total", label: "total time" },
] as const;

// One panel per state, in parallel — admin-only and infrequent, so N small requests cost less
// than the batched query and its own cache invalidation would.
async function fetchAllPanels(kind: PipelineKind): Promise<PipelinePanel[]> {
  const states: { code: string }[] = await fetchJurisdictionStates();
  const panels = await Promise.all(states.map((s) => fetchPipelinePanel(s.code, kind)));
  return panels.sort((a: PipelinePanel, b: PipelinePanel) => a.state.localeCompare(b.state));
}

// Run time is measured for the scrape only, so the other pipelines show cost and no time.
function passAverages(panel: PipelinePanel, fleet: GlobalPanel): PassAverages {
  const scrape = panel.kind === PipelineKind.PEOPLE;
  return {
    cost_per_run_usd: scrape ? fleet.cost_per_run_this_month_usd : panel.cost_per_run_this_month_usd,
    seconds_per_run: scrape ? fleet.seconds_per_run_this_month : null,
    concurrency: fleet.pipeline_run_concurrency,
  };
}

function renderPipelineSwitch(current: PipelineKind, onPick: (kind: PipelineKind) => void) {
  return html`
    <div class="pipelines-page__switch" role="group" aria-label="Pipeline">
      ${PIPELINE_KINDS.map(
        (kind) => html`<button
          class="pipelines-page__switch-btn"
          aria-pressed=${kind === current}
          @click=${() => onPick(kind)}
        >
          ${PIPELINE_LABELS[kind]}
        </button>`,
      )}
    </div>
  `;
}

function renderFigure(value: string, label: TemplateResult | string) {
  return html`
    <span class="pipelines-page__ledger-figure">
      <span class="pipelines-page__ledger-n">${value}</span>
      <span class="pipelines-page__ledger-label">${label}</span>
    </span>
  `;
}

function renderLedger(panel: GlobalPanel, canEdit: boolean, onEdit: () => void) {
  const cap = panel.monthly_cap_usd === null ? "no cap" : `of ${formatUsd(panel.monthly_cap_usd)}`;
  const cost = panel.cost_per_run_this_month_usd;
  const seconds = panel.seconds_per_run_this_month;
  return html`
    <div class="pipelines-page__ledger">
      ${renderFigure(
        formatUsd(panel.spent_this_month_usd),
        html`this month, ${cap}
        ${canEdit
          ? html`<button class="pipelines-page__edit" @click=${onEdit}>edit</button>`
          : nothing}`,
      )}
      ${cost !== null ? renderFigure(formatUsd(cost), "avg per run") : nothing}
      ${seconds !== null ? renderFigure(formatDuration(seconds), "avg run time") : nothing}
    </div>
  `;
}

const ESTIMATE_NOTE_ID = "pipelines-estimate-note";

function renderEstimateNote(concurrency: number) {
  return html`
    <button
      class="pipelines-page__info"
      popovertarget=${ESTIMATE_NOTE_ID}
      aria-label="How the estimates are worked out"
    >
      <i class="fa-solid fa-circle-info" aria-hidden="true"></i>
    </button>
    <div id=${ESTIMATE_NOTE_ID} popover class="pipelines-page__popover">
      Wall-clock is how long the pass takes: due runs go ${concurrency} at a time, each batch
      taking about one average run. Total is every run's time added up, which is what counts
      against rate limits. The average run is this month's successful runs, measured from when
      each was queued to when it finished.
    </div>
  `;
}

function renderHead(fleet: GlobalPanel | null) {
  return html`
    <div class="pipelines-page__row pipelines-page__row--head">
      <span class="pipelines-page__row-state">state</span>
      ${COLS.map(
        (col) =>
          html`<span class="pipelines-page__row-fig pipelines-page__row-fig--${col.key}"
            >${col.label}${col.key === "wall-clock" && fleet
              ? renderEstimateNote(fleet.pipeline_run_concurrency)
              : nothing}</span
          >`,
      )}
      <span></span>
      <span></span>
    </div>
  `;
}

function renderRow(
  panel: PipelinePanel,
  fleet: GlobalPanel | null,
  onEdit: (state: string) => void,
  onScrapeClick: (state: string) => void,
  starting: string | null,
  scrapeError: string | null,
) {
  const overBudget = panel.cap_reached !== null;
  const anchor = describeAnchor(panel);
  const nextPass = fleet ? describeNextPass(panel.candidates_due, passAverages(panel, fleet)) : null;
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
        ${describePerRun(panel.cost_per_run_this_month_usd, panel.pipeline_run_cap_usd)}
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
        ${panel.candidates_due ? `${panel.candidates_due} due` : "none"}
      </span>
      <span class="pipelines-page__row-fig pipelines-page__row-fig--est-cost">
        ${nextPass?.cost}
      </span>
      <span class="pipelines-page__row-fig pipelines-page__row-fig--wall-clock">
        ${nextPass?.wall_clock}
      </span>
      <span class="pipelines-page__row-fig pipelines-page__row-fig--total">
        ${nextPass?.total}
      </span>
      <button class="pipelines-page__edit" @click=${() => onEdit(panel.state)}>edit</button>
      <span class="pipelines-page__scrape">
        <button
          class="btn btn-sm pipelines-page__scrape-btn"
          ?disabled=${starting === panel.state}
          @click=${() => onScrapeClick(panel.state)}
        >
          ${starting === panel.state ? "Starting…" : "Run now"}
        </button>
        ${scrapeError ? html`<span class="pipelines-page__scrape-error">${scrapeError}</span>` : nothing}
      </span>
    </div>
  `;
}

function PipelinesPage() {
  const { permissions } = useAuth();
  const [pipeline, setPipeline] = useState<PipelineKind>(getPipelineFromUrl());
  const [panels, setPanels] = useState<PipelinePanel[] | null>(null);
  const [budget, setBudget] = useState<GlobalPanel | null>(null);
  const [editingBudget, setEditingBudget] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingState, setEditingState] = useState<string | null>(null);
  const [confirmingState, setConfirmingState] = useState<string | null>(null);
  const [starting, setStarting] = useState<string | null>(null);
  const [scrapeErrors, setScrapeErrors] = useState<Record<string, string>>({});

  // Every state unless the URL names one: the table above lists them all.
  const runsStateCode = getStateFromUrl();
  const [runs, setRuns] = useState<any[]>([]);
  const [runsPage, setRunsPage] = useState(getIntParam("runs_page", 1));
  const [runsPerPage, setRunsPerPage] = useState(
    getIntParam("runs_per_page", 25, RUNS_PER_PAGE_CHOICES),
  );
  const [runsTotalPages, setRunsTotalPages] = useState(1);
  const [runsLoaded, setRunsLoaded] = useState(false);

  const load = () => {
    setPanels(null);
    fetchAllPanels(pipeline)
      .then(setPanels)
      .catch((err: Error) => setError(err.message));
  };

  const loadBudget = () => {
    fetchGlobalPipelineSettings()
      .then(setBudget)
      .catch(() => setBudget(null));
  };

  const pickPipeline = (kind: PipelineKind) => {
    setPipelineInUrl(kind);
    setPipeline(kind);
  };

  useEffect(load, [pipeline]);
  useEffect(loadBudget, []);

  useEffect(() => {
    const onPopState = () => {
      setPipeline(getPipelineFromUrl());
      setRunsPage(getIntParam("runs_page", 1));
      setRunsPerPage(getIntParam("runs_per_page", 25, RUNS_PER_PAGE_CHOICES));
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const loadRuns = () => {
    fetchActivePipelineRuns(runsStateCode || undefined, runsPage, runsPerPage)
      .then((result: any) => {
        setRuns(result.data || []);
        setRunsTotalPages(result.total_pages || 1);
      })
      .catch(() => setRuns([]))
      .finally(() => setRunsLoaded(true));
  };

  // Always, not only while runs exist: a batch registers its runs after Scrape now returns.
  useEffect(() => {
    loadRuns();
    const timer = setInterval(loadRuns, RUNS_POLL_MS);
    return () => clearInterval(timer);
  }, [runsStateCode, runsPage, runsPerPage]);

  const handleRunsPerPageChange = (e: Event) => {
    const n = parseInt((e.target as HTMLSelectElement).value, 10);
    setRunsParamsInUrl(1, n);
    setRunsPerPage(n);
    setRunsPage(1);
  };

  const editingPanel = panels?.find((p) => p.state === editingState) ?? null;

  // Confirmed, not fired on click: a batch spends real money and cannot be recalled.
  const confirmScrape = () => {
    const state = confirmingState as string;
    setConfirmingState(null);
    setStarting(state);
    setScrapeErrors((prev) => ({ ...prev, [state]: "" }));
    startStatePass(pipeline, state)
      .catch((err: Error) => setScrapeErrors((prev) => ({ ...prev, [state]: err.message })))
      .finally(() => setStarting(null));
  };

  if (error) return html`<main class="pipelines-page page-content"><p class="pipelines-page__empty">${error}</p></main>`;

  return html`
    <main class="pipelines-page page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Pipelines</h1>
        ${budget
          ? html`<div class="page-focal__end">
              ${renderLedger(budget, !!permissions.can_write_global_config, () =>
                setEditingBudget(true),
              )}
            </div>`
          : nothing}
      </div>

      <div class="sectioned">
      ${SectionNav("admin", adminSection(permissions), "/pipelines")}
      <div class="secbody">

      ${editingBudget && budget
        ? html`<civ-global-budget-modal
            .panel=${budget}
            @settings-saved=${() => {
              setEditingBudget(false);
              loadBudget();
            }}
            @cancel=${() => setEditingBudget(false)}
          ></civ-global-budget-modal>`
        : nothing}

      ${renderPipelineSwitch(pipeline, pickPipeline)}
      ${panels
        ? html`<div class="pipelines-page__list">
            ${renderHead(budget)}
            ${panels.map((panel) =>
              renderRow(panel, budget, setEditingState, setConfirmingState, starting, scrapeErrors[panel.state] || null),
            )}
          </div>`
        : html`<p class="pipelines-page__empty">Loading…</p>`}

      ${runsLoaded && runs.length === 0
        ? html`<p class="pipelines-page__empty">No runs in progress.</p>`
        : html`<pipeline-runs-list
            .jobs=${runs}
            .page=${runsPage}
            .totalPages=${runsTotalPages}
            .perPage=${runsPerPage}
            .onPageChange=${(p: number) => {
              setRunsParamsInUrl(p, runsPerPage);
              setRunsPage(p);
            }}
            .onPerPageChange=${handleRunsPerPageChange}
            .canCancel=${permissions.can_cancel_pipeline_run}
            .onCancel=${(pipelineRunId: string) =>
              setRuns((prev) => prev.filter((j) => j.pipeline_run_id !== pipelineRunId))}
          ></pipeline-runs-list>`}

      ${editingPanel
        ? html`<civ-pipeline-settings-modal
            .panel=${editingPanel}
            @settings-saved=${() => {
              setEditingState(null);
              load();
            }}
            @cancel=${() => setEditingState(null)}
          ></civ-pipeline-settings-modal>`
        : nothing}

      ${confirmingState
        ? html`<civ-confirm-modal
            .title=${`Run ${PIPELINE_LABELS[pipeline].toLowerCase()} for ${confirmingState.toUpperCase()}?`}
            .message=${`Runs every jurisdiction in ${confirmingState.toUpperCase()} that is due, however many that is. They cost money to run and cannot be stopped once started.`}
            .confirmLabel=${"Start"}
            .variant=${"danger"}
            @confirm=${confirmScrape}
            @cancel=${() => setConfirmingState(null)}
          ></civ-confirm-modal>`
        : nothing}
      </div>
      </div>
    </main>
  `;
}

customElements.define("pipelines-page", component(PipelinesPage as any, { useShadowDOM: false }));
