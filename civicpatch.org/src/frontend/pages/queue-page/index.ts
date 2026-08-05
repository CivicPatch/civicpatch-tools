import "./queue-page.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { STORAGE_KEYS } from "../../utils/storage-keys.js";
import { usePullRequestActions } from "../../hooks/use-pull-request-actions.js";
import { config } from "../../assets/config.js";
import {
  fetchPullRequestsWithData,
  fetchActivePipelineRuns,
} from "../../api.js";
import "../../components/publish-log/index.js";
import "./queue-summary/index.js";
import "./active-jobs/index.js";
import "./pr-list/index.js";

const API_URL = config.apiUrl;

type PrItem = {
  pr: { number: number };
  jurisdiction?: { name?: string; ocdid?: string };
};

type PrActionDetail = {
  pullRequestNumber: number;
  request_id: string;
  jurisdiction_ocdid: string;
};

function getIntParam(key: string, fallback: number, allowed: number[] | null = null): number {
  const val = parseInt(new URLSearchParams(window.location.search).get(key) ?? "", 10);
  if (isNaN(val) || val < 1) return fallback;
  if (allowed && !allowed.includes(val)) return fallback;
  return val;
}

function getStateFromUrl(): string {
  const val = new URLSearchParams(window.location.search).get("state");
  return val ? val.toLowerCase() : "";
}

function getViewFromUrl(): "detail" | "quick" | null {
  const val = new URLSearchParams(window.location.search).get("view");
  return val === "detail" ? "detail" : val === "quick" ? "quick" : null;
}

function setPrParamsInUrl(page: number, perPage: number): void {
  const params = new URLSearchParams(window.location.search);
  params.set("pr_page", String(page));
  params.set("pr_per_page", String(perPage));
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function setAjParamsInUrl(page: number, perPage: number): void {
  const params = new URLSearchParams(window.location.search);
  params.set("aj_page", String(page));
  params.set("aj_per_page", String(perPage));
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function QueuePage() {
  const { permissions } = useAuth();
  const [defaultState] = useLocalStorage(STORAGE_KEYS.DEFAULT_STATE, "", { ttl: PERSIST_FOREVER });
  const [defaultView, setDefaultView] = useLocalStorage(STORAGE_KEYS.QUEUE_VIEW, "quick", { ttl: PERSIST_FOREVER });
  const stateCode = (getStateFromUrl() || defaultState || "").toLowerCase();
  const [queueSummary, setQueueSummary] = useState<any>(null);
  const [pullRequests, setPullRequests] = useState<PrItem[]>([]);
  const { actionState, entries: publishLogEntries, trackMerge, trackClose } = usePullRequestActions();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(getIntParam("pr_page", 1));
  const [perPage, setPerPage] = useState(getIntParam("pr_per_page", 10, [10, 25, 50]));
  const [totalPages, setTotalPages] = useState(1);
  const [viewMode, setViewMode] = useState<string>(getViewFromUrl() || defaultView);
  const [activePipelineRuns, setActivePipelineRuns] = useState<any[]>([]);
  const [activePipelineRunsPage, setActivePipelineRunsPage] = useState(getIntParam("aj_page", 1));
  const [activePipelineRunsTotalPages, setActivePipelineRunsTotalPages] = useState(1);
  const [activePipelineRunsPerPage, setActivePipelineRunsPerPage] = useState(getIntParam("aj_per_page", 25, [10, 25, 50]));

  useEffect(() => {
    const onPopState = () => {
      setPage(getIntParam("pr_page", 1));
      setPerPage(getIntParam("pr_per_page", 10, [10, 25, 50]));
      setActivePipelineRunsPage(getIntParam("aj_page", 1));
      setActivePipelineRunsPerPage(getIntParam("aj_per_page", 25, [10, 25, 50]));
      setViewMode(getViewFromUrl() || defaultView);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (!stateCode) return;
    setLoading(true);
    setError(null);
    fetchPullRequestsWithData(stateCode, page, perPage, viewMode)
      .then((result: any) => {
        setPullRequests(result.data || []);
        setQueueSummary(result.summary || null);
        setTotalPages(result.total_pages || 1);
      })
      .catch((err: any) => setError(err.message))
      .finally(() => setLoading(false));
  }, [stateCode, page, perPage, viewMode]);

  useEffect(() => {
    fetchActivePipelineRuns(stateCode || undefined, activePipelineRunsPage, activePipelineRunsPerPage)
      .then((result: any) => {
        setActivePipelineRuns(result.data || []);
        setActivePipelineRunsTotalPages(result.total_pages || 1);
      })
      .catch(() => setActivePipelineRuns([]));
  }, [stateCode, activePipelineRunsPage, activePipelineRunsPerPage]);

  const handleMerge = (event: CustomEvent<PrActionDetail>) => {
    const { pullRequestNumber, request_id, jurisdiction_ocdid } = event.detail;
    const pr = pullRequests.find((p) => p.pr.number === pullRequestNumber);
    trackMerge(pullRequestNumber, request_id, jurisdiction_ocdid, null, pr?.jurisdiction?.name ?? `#${pullRequestNumber}`);
  };

  const handleClose = (event: CustomEvent<PrActionDetail>) => {
    const { pullRequestNumber, request_id } = event.detail;
    const pr = pullRequests.find((p) => p.pr.number === pullRequestNumber);
    trackClose(pullRequestNumber, request_id, pr?.jurisdiction?.name ?? `#${pullRequestNumber}`);
  };

  const handleViewChange = (newView: string) => {
    const params = new URLSearchParams(window.location.search);
    params.set("view", newView);
    window.history.pushState({}, "", `${window.location.pathname}?${params}`);
    setDefaultView(newView);
    setViewMode(newView);
  };

  const handleCancel = (requestId: string) => {
    setActivePipelineRuns((prev) => prev.filter((j) => j.request_id !== requestId));
  };

  const handleActivePipelineRunsPerPageChange = (e: Event) => {
    const n = parseInt((e.target as HTMLSelectElement).value, 10);
    setAjParamsInUrl(1, n);
    setActivePipelineRunsPerPage(n);
    setActivePipelineRunsPage(1);
  };

  const handlePageChange = (newPage: number) => {
    setPrParamsInUrl(newPage, perPage);
    setPage(newPage);
  };

  const handlePerPageChange = (e: Event) => {
    const newPerPage = parseInt((e.target as HTMLSelectElement).value, 10);
    setPrParamsInUrl(1, newPerPage);
    setPerPage(newPerPage);
    setPage(1);
  };

  return html`
    <main class="queue-page page-content">
      ${permissions.can_view_queue_page_errors ? html`
        <div class="queue-page__filters">
          <div class="queue-page__filters-right">
            <a class="btn btn-sm" href="${API_URL}/api/v1/requests/people-export.csv?state=${stateCode}" download>Export people</a>
            <a class="btn btn-sm" href="${API_URL}/api/v1/requests/export.csv?state=${stateCode}" download>Export queue</a>
          </div>
        </div>
      ` : null}

      ${!stateCode ? html`<p class="queue-page__select-state-prompt">Select a state to get started.</p>` : null}

      ${stateCode ? html`
        ${queueSummary ? html`<queue-summary .summary=${queueSummary}></queue-summary>` : null}
        <queue-active-pipeline-runs
          .jobs=${activePipelineRuns}
          .page=${activePipelineRunsPage}
          .totalPages=${activePipelineRunsTotalPages}
          .perPage=${activePipelineRunsPerPage}
          .onPageChange=${(p: number) => { setAjParamsInUrl(p, activePipelineRunsPerPage); setActivePipelineRunsPage(p); }}
          .onPerPageChange=${handleActivePipelineRunsPerPageChange}
          .canCancel=${permissions.can_cancel_job}
          .onCancel=${handleCancel}
        ></queue-active-pipeline-runs>
        <queue-pr-list
          .pullRequests=${pullRequests}
          .pullRequestState=${actionState}
          .loading=${loading}
          .error=${error}
          .page=${page}
          .perPage=${perPage}
          .totalPages=${totalPages}
          .viewMode=${viewMode}
          @onMerge=${handleMerge}
          @onClose=${handleClose}
          .onViewChange=${handleViewChange}
          .onPageChange=${handlePageChange}
          .onPerPageChange=${handlePerPageChange}
        ></queue-pr-list>
      ` : null}
    </main>
    <civ-publish-log .entries=${publishLogEntries}></civ-publish-log>
  `;
}

customElements.define("queue-page", component(QueuePage, { useShadowDOM: false }));
export default QueuePage;
