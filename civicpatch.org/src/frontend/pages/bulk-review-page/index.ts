import "./bulk-review-page.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { STORAGE_KEYS } from "../../utils/storage-keys.js";
import { useReviewActions } from "../../hooks/use-review-actions.js";
import { config } from "../../assets/config.js";
import {
  fetchPullRequestsWithData,
} from "../../api.js";
import "../../components/review-log/index.js";
import "./summary/index.js";
import "./review-card-list/index.js";

const API_URL = config.apiUrl;

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

function BulkReviewPage() {
  const { permissions } = useAuth();
  const [defaultState] = useLocalStorage(STORAGE_KEYS.DEFAULT_STATE, "", { ttl: PERSIST_FOREVER });
  const [defaultView, setDefaultView] = useLocalStorage(STORAGE_KEYS.QUEUE_VIEW, "quick", { ttl: PERSIST_FOREVER });
  const stateCode = (getStateFromUrl() || defaultState || "").toLowerCase();
  const [summary, setSummary] = useState<any>(null);
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
    if (!stateCode) return;
    setLoading(true);
    setError(null);
    fetchPullRequestsWithData(stateCode, page, perPage, viewMode)
      .then((result: any) => {
        setPullRequests(result.data || []);
        setSummary(result.summary || null);
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
        ${stateCode && summary
          ? html`<bulk-review-summary .summary=${summary}></bulk-review-summary>`
          : null}
        ${permissions.can_view_queue_page_errors
          ? html`<a class="page-focal__end btn btn-sm" href="${API_URL}/api/v1/requests/people-export.csv?state=${stateCode}" download>Export people</a>`
          : null}
      </div>

      ${!stateCode ? html`<p class="bulk-review__select-state-prompt">Select a state to get started.</p>` : null}

      ${stateCode ? html`
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
      ` : null}
    </main>
    <civ-review-log .entries=${reviewLogEntries}></civ-review-log>
  `;
}

customElements.define("bulk-review-page", component(BulkReviewPage, { useShadowDOM: false }));
export default BulkReviewPage;
