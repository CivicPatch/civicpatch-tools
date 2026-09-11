import "./bulk-review-page.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { STORAGE_KEYS } from "../../utils/storage-keys.js";
import { useReviewActions } from "../../hooks/use-review-actions.js";
import {
  fetchPullRequestsWithData,
} from "../../api.js";
import "../../components/review-log/index.js";
import "./review-card-list/index.js";
import { SectionNav, manageSection } from "../../components/section-nav/index.js";
import "../../components/select-state/select-state.js";
import { useSummary } from "../../hooks/useSummary.js";

type PrItem = {
  changeset_id: string;
  pr?: { number: number };
  jurisdiction?: { name?: string; ocdid?: string };
};

type PrActionDetail = {
  changeset_id: string;
  jurisdiction_ocdid: string;
};

function getIntParam(key: string, fallback: number, allowed: number[] | null = null): number {
  const val = parseInt(new URLSearchParams(window.location.search).get(key) ?? "", 10);
  if (isNaN(val) || val < 1) return fallback;
  if (allowed && !allowed.includes(val)) return fallback;
  return val;
}

const STATE_QUERY_KEY = "state";

function getStateFromUrl(): string {
  const val = new URLSearchParams(window.location.search).get(STATE_QUERY_KEY);
  return val ? val.toLowerCase() : "";
}

// Bulk review spans every state by default now — an unfiltered queue is a valid
// worklist, not an error state — so this is its own filter with its own URL param,
// not a fallback to the navbar's stored default.
function setStateInUrl(code: string): void {
  const params = new URLSearchParams(window.location.search);
  if (code) params.set(STATE_QUERY_KEY, code);
  else params.delete(STATE_QUERY_KEY);
  const qs = params.toString();
  window.history.replaceState({}, "", `${window.location.pathname}${qs ? "?" + qs : ""}`);
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

function BulkReviewPage() {
  const { permissions } = useAuth();
  const [defaultView, setDefaultView] = useLocalStorage(STORAGE_KEYS.QUEUE_VIEW, "quick", { ttl: PERSIST_FOREVER });
  const [stateCode, setStateCode] = useState(getStateFromUrl());
  const handleStateChange = (e: CustomEvent<{ state: string }>) => {
    const code = (e.detail.state || "").toLowerCase();
    setStateCode(code);
    setStateInUrl(code);
  };
  // Global, not scoped to this page's own state filter — the sidebar badge is a
  // constant "how much is waiting overall" figure, the same wherever it appears.
  const globalSummary = useSummary(true, "");
  const [pullRequests, setPullRequests] = useState<PrItem[]>([]);
  const { actionState, entries: reviewLogEntries, trackApprove, trackReject } = useReviewActions();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(getIntParam("pr_page", 1));
  const [perPage, setPerPage] = useState(getIntParam("pr_per_page", 10, [10, 25, 50]));
  const [totalPages, setTotalPages] = useState(1);
  const [viewMode, setViewMode] = useState<string>(getViewFromUrl() || defaultView);

  useEffect(() => {
    const onPopState = () => {
      setPage(getIntParam("pr_page", 1));
      setPerPage(getIntParam("pr_per_page", 10, [10, 25, 50]));
      setViewMode(getViewFromUrl() || defaultView);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchPullRequestsWithData(stateCode, page, perPage, viewMode)
      .then((result: any) => {
        setPullRequests(result.data || []);
        setTotalPages(result.total_pages || 1);
      })
      .catch((err: any) => setError(err.message))
      .finally(() => setLoading(false));
  }, [stateCode, page, perPage, viewMode]);

  const handleApprove = (event: CustomEvent<PrActionDetail>) => {
    const { changeset_id, jurisdiction_ocdid } = event.detail;
    const pr = pullRequests.find((p) => p.changeset_id === changeset_id);
    trackApprove(changeset_id, jurisdiction_ocdid, null, pr?.jurisdiction?.name ?? changeset_id);
  };

  const handleReject = (event: CustomEvent<PrActionDetail>) => {
    const { changeset_id } = event.detail;
    const pr = pullRequests.find((p) => p.changeset_id === changeset_id);
    trackReject(changeset_id, pr?.jurisdiction?.name ?? changeset_id);
  };

  const handleViewChange = (newView: string) => {
    const params = new URLSearchParams(window.location.search);
    params.set("view", newView);
    window.history.pushState({}, "", `${window.location.pathname}?${params}`);
    setDefaultView(newView);
    setViewMode(newView);
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
    <main class="bulk-review page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Bulk review</h1>
      </div>

      <div class="sectioned">
        ${SectionNav("manage", manageSection(permissions, globalSummary?.open_prs), "/bulk-review")}
        <div class="secbody">
          <div class="bulk-review__state-filter">
            <label>State</label>
            <civ-select-state .selected=${stateCode} @state-change=${handleStateChange}></civ-select-state>
          </div>

          <bulk-review-card-list
            .cards=${pullRequests}
            .actionState=${actionState}
            .loading=${loading}
            .error=${error}
            .page=${page}
            .perPage=${perPage}
            .totalPages=${totalPages}
            .viewMode=${viewMode}
            @approve=${handleApprove}
            @reject=${handleReject}
            .onViewChange=${handleViewChange}
            .onPageChange=${handlePageChange}
            .onPerPageChange=${handlePerPageChange}
          ></bulk-review-card-list>
        </div>
      </div>
    </main>
    <civ-review-log .entries=${reviewLogEntries}></civ-review-log>
  `;
}

customElements.define("bulk-review-page", component(BulkReviewPage, { useShadowDOM: false }));
export default BulkReviewPage;
