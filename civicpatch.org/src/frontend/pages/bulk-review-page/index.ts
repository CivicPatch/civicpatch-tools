import "./bulk-review-page.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import {
  dismissReviewSelection,
  fetchPullRequestsWithData,
  publishReviewSelection,
} from "../../api.js";
import "./bulk-review-list.js";
import type { QueueRow } from "./bulk-review-list.js";
import type { PublishResult } from "../import-page/import-types.js";
import { SectionNav, manageSection } from "../../components/section-nav/index.js";
import "../../components/select-state/select-state.js";
import { useSummary } from "../../hooks/useSummary.js";

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

function setPrParamsInUrl(page: number, perPage: number): void {
  const params = new URLSearchParams(window.location.search);
  params.set("pr_page", String(page));
  params.set("pr_per_page", String(perPage));
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function BulkReviewPage() {
  const { permissions } = useAuth();
  const [stateCode, setStateCode] = useState(getStateFromUrl());
  const handleStateChange = (e: CustomEvent<{ state: string }>) => {
    const code = (e.detail.state || "").toLowerCase();
    setStateCode(code);
    setStateInUrl(code);
    setSelected([]);
  };
  // Global, not scoped to this page's own state filter — the sidebar badge is a
  // constant "how much is waiting overall" figure, the same wherever it appears.
  const globalSummary = useSummary(true, "");
  const [rows, setRows] = useState<QueueRow[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<PublishResult[]>([]);
  // Bumped after a publish or dismiss: the pool has changed, so the page is re-read.
  const [reloads, setReloads] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(getIntParam("pr_page", 1));
  const [perPage, setPerPage] = useState(getIntParam("pr_per_page", 10, [10, 25, 50]));
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    const onPopState = () => {
      setPage(getIntParam("pr_page", 1));
      setPerPage(getIntParam("pr_per_page", 10, [10, 25, 50]));
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchPullRequestsWithData(stateCode, page, perPage)
      .then((result: { data?: QueueRow[]; total_pages?: number }) => {
        setRows(result.data || []);
        setTotalPages(result.total_pages || 1);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [stateCode, page, perPage, reloads]);

  const decide = async (action: (ids: string[]) => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action(selected);
      setSelected([]);
      setReloads(reloads + 1);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const handlePublish = () =>
    decide(async (ids) => {
      const { data } = await publishReviewSelection(ids);
      setResults(data);
    });

  const handleDismiss = () =>
    decide(async (ids) => {
      await dismissReviewSelection(ids);
      setResults([]);
    });

  const handleSelection = (e: CustomEvent<{ selected: string[] }>) =>
    setSelected(e.detail.selected);

  const handlePageChange = (newPage: number) => {
    setPrParamsInUrl(newPage, perPage);
    setPage(newPage);
    setSelected([]);
  };

  const handlePerPageChange = (e: Event) => {
    const newPerPage = parseInt((e.target as HTMLSelectElement).value, 10);
    setPrParamsInUrl(1, newPerPage);
    setPerPage(newPerPage);
    setPage(1);
    setSelected([]);
  };

  const failed = results.filter((result) => !result.published);

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

          ${results.length
            ? html`<section class="bulk-review__results">
                <p>Published ${results.length - failed.length} of ${results.length}.</p>
                ${failed.map(
                  (result) => html`<p class="bulk-review__failure">
                    ${result.jurisdiction_ocdid}: ${result.error}
                  </p>`,
                )}
              </section>`
            : null}

          <bulk-review-list
            .rows=${rows}
            .selected=${selected}
            .busy=${busy}
            .loading=${loading}
            .error=${error}
            .page=${page}
            .perPage=${perPage}
            .totalPages=${totalPages}
            .onPageChange=${handlePageChange}
            .onPerPageChange=${handlePerPageChange}
            @selection-change=${handleSelection}
            @publish-selection=${handlePublish}
            @dismiss-selection=${handleDismiss}
          ></bulk-review-list>
        </div>
      </div>
    </main>
  `;
}

customElements.define("bulk-review-page", component(BulkReviewPage, { useShadowDOM: false }));
export default BulkReviewPage;
