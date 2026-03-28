import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import {
  fetchPullRequestsWithData,
  fetchJobsWithErrors,
  saveAndMerge,
  closePullRequest,
  resolveJob,
  fetchDuplicatePrJurisdictionJobs,
  fetchPullRequests,
  closeStaleDuplicatePrs,
} from "../../api.js";
import { pullRequestUrlToNumber } from "../../components/pull-request-card/pr-utils.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import "../../components/pull-request-card/index.js";
import "./error-card/index.js";
import "../../components/stat-cards/index.js";
import "../../components/search-jurisdictions/select-state.js";

const DEFAULT_STATE = "tx";
const DEFAULT_PER_PAGE = 20;
const PER_PAGE_OPTIONS = [10, 20, 50, 100];

function getPageFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const page = parseInt(params.get("page"), 10);
  return isNaN(page) || page < 1 ? 1 : page;
}

function getStateFromUrl() {
  return (new URLSearchParams(window.location.search).get("state") || DEFAULT_STATE).toLowerCase();
}

function getPerPageFromUrl() {
  const val = parseInt(new URLSearchParams(window.location.search).get("per_page"), 10);
  return PER_PAGE_OPTIONS.includes(val) ? val : DEFAULT_PER_PAGE;
}

function setPageInUrl(page) {
  const params = new URLSearchParams(window.location.search);
  params.set("page", page);
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function getPageRange(page, totalPages) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const delta = 2;
  const pages = new Set([1, totalPages]);
  for (let i = page - delta; i <= page + delta; i++) {
    if (i >= 1 && i <= totalPages) pages.add(i);
  }
  const sorted = Array.from(pages).sort((a, b) => a - b);
  const result = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] === 2) {
      result.push(sorted[i - 1] + 1);
    } else if (i > 0 && sorted[i] - sorted[i - 1] > 2) {
      result.push("...");
    }
    result.push(sorted[i]);
  }
  return result;
}

function JobsPage() {
  const { permissions } = useAuth(); 
  const [stateCode, setStateCode] = useState(getStateFromUrl());
  const [page, setPage] = useState(getPageFromUrl());
  const [total, setTotal] = useState(0);

  const [jobsSummary, setJobsSummary] = useState(null);

  const [duplicateJurisdictions, setDuplicateJurisdictions] = useState([]);
  const [duplicateJurisdictionPRs, setDuplicateJurisdictionPRs] = useState({});
  const [openJurisdictions, setOpenJurisdictions] = useState({});
  const [closingStale, setClosingStale] = useState(false);
  const [pullRequests, setPullRequests] = useState([]);
  const [pullRequestState, setPullRequestState] = useState({});

  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);

  const [errorJobs, setErrorJobs] = useState([]);
  const [error, setError] = useState(null);
  const [perPage, setPerPage] = useState(getPerPageFromUrl());

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (!params.get("state")) {
      params.set("state", stateCode);
      if (!params.get("page")) params.set("page", page);
      if (!params.get("per_page")) params.set("per_page", perPage);
      window.history.replaceState({}, "", `${window.location.pathname}?${params}`);
    }
    const onPopState = () => {
      setPage(getPageFromUrl());
      setPerPage(getPerPageFromUrl());
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      fetchPullRequestsWithData(page, perPage, stateCode.toLowerCase()),
      fetchJobsWithErrors(stateCode.toLowerCase()),
      fetchDuplicatePrJurisdictionJobs(),
    ])
      .then(([prResult, errResult, duplicatePrResult]) => {
        setPullRequests(prResult.data || []);
        setTotal(prResult.total || 0);
        setErrorJobs(errResult.data || []);
        setJobsSummary(prResult.summary || null);
        // Expecting duplicatePrResult.jurisdiction_ocdids or .data as array of ocdids
        setDuplicateJurisdictions(
          duplicatePrResult.data || []
        );
      })
      .catch((err) => setError(err.message))
      .finally(() => { setLoading(false); setPageLoading(false); });
  }, [page, stateCode]);

  const handleMerge = async (event) => {
    const { pullRequestNumber, request_id, jurisdiction_ocdid } = event.detail;
    try {
      setPullRequestState({
        ...pullRequestState,
        [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_MERGE },
      });
      await saveAndMerge(pullRequestNumber, request_id, jurisdiction_ocdid, null);
      setPullRequestState({
        ...pullRequestState,
        [pullRequestNumber]: { status: PULL_REQUEST_STATUS.MERGED },
      });
    } catch (error) {
      setPullRequestState({
        ...pullRequestState,
        [pullRequestNumber]: { status: PULL_REQUEST_STATUS.ERROR, error },
      });
    }
  };

  const handleClose = async (event) => {
    const pullRequestNumber = event.detail.pullRequestNumber;
    const request_id = event.detail.request_id;
    try {
      setPullRequestState({
        ...pullRequestState,
        [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_CLOSE },
      });
      await closePullRequest(request_id, pullRequestNumber);
      setPullRequestState({
        ...pullRequestState,
        [pullRequestNumber]: { status: PULL_REQUEST_STATUS.CLOSED },
      });
    } catch (error) {
      setPullRequestState({
        ...pullRequestState,
        [pullRequestNumber]: { status: PULL_REQUEST_STATUS.ERROR, error },
      });
    }
  };

  const handleResolveError = async (event) => {
    const { job } = event.detail;
    try {
      await resolveJob(job.request_id);
      setErrorJobs(errorJobs.filter((j) => j.request_id !== job.request_id));
    } catch (err) {
      console.error("Failed to resolve job:", err);
    }
  };

  const handleStateChange = (e) => {
    const newState = e.detail.state;
    const params = new URLSearchParams(window.location.search);
    params.set("state", newState);
    params.set("page", 1);
    window.history.pushState({}, "", `${window.location.pathname}?${params}`);
    setStateCode(newState);
    setPage(1);
  };

  const goToPage = (newPage) => {
    setPageLoading(true);
    setPageInUrl(newPage);
    setPage(newPage);
  };

  const handlePerPageChange = (e) => {
    const newPerPage = parseInt(e.target.value, 10);
    const params = new URLSearchParams(window.location.search);
    params.set("per_page", newPerPage);
    params.set("page", 1);
    window.history.pushState({}, "", `${window.location.pathname}?${params}`);
    setPerPage(newPerPage);
    setPage(1);
  };

  const totalPages = Math.ceil(total / perPage);

  const handleCloseStaleDuplicates = async () => {
    setClosingStale(true);
    try {
      await closeStaleDuplicatePrs();
      const result = await fetchDuplicatePrJurisdictionJobs();
      setDuplicateJurisdictions(result.data || []);
      setDuplicateJurisdictionPRs({});
      setOpenJurisdictions({});
    } finally {
      setClosingStale(false);
    }
  };

  // Lazy-load PRs for a jurisdiction_ocdid and toggle accordion open state
  const loadJurisdictionPRs = async (ocdid) => {
    setOpenJurisdictions((prev) => ({ ...prev, [ocdid]: !prev[ocdid] }));
    if (!duplicateJurisdictionPRs[ocdid]) {
      const prs = await fetchPullRequests(ocdid);
      setDuplicateJurisdictionPRs((prev) => ({ ...prev, [ocdid]: prs.data || [] }));
    }
  };

  const duplicatePrList = duplicateJurisdictions.map((ocdid) => {
    const isOpen = openJurisdictions[ocdid];
    return html`
      <div class="jobs-page__duplicate-item">
        <button
          class="jobs-page__duplicate-item-header${isOpen ? ' jobs-page__duplicate-item-header--open' : ''}"
          @click=${() => loadJurisdictionPRs(ocdid)}
        >
          <span>${ocdid}</span>
          <span class="jobs-page__duplicate-chevron">▼</span>
        </button>
        ${isOpen ? html`
          <div class="jobs-page__duplicate-item-body">
            ${(duplicateJurisdictionPRs[ocdid] || []).map((pr) => {
              const pullRequestNumber = pullRequestUrlToNumber(pr.pull_request_url);
              return html`
                <pr-card
                  @onMerge=${handleMerge}
                  @onClose=${handleClose}
                  .pr=${pr}
                  .state=${pullRequestState[pullRequestNumber]}
                  .data=${{
                    existing: pr.existing,
                    pull_request: pr.pull_request,
                  }}
                ></pr-card>
              `;
            })}
          </div>
        ` : null}
      </div>
    `;
  });

  const prList = loading
    ? html`<div>Loading...</div>`
    : error
      ? html`<div>Error: ${error}</div>`
      : pullRequests.length === 0
        ? html`<p>No pull requests found.</p>`
        : pullRequests.map((pr) => {
            const pullRequestNumber = pullRequestUrlToNumber(pr.details.pull_request_url);
            return html`
              <pr-card
                @onMerge=${handleMerge}
                @onClose=${handleClose}
                .pr=${pr.details}
                .state=${pullRequestState[pullRequestNumber]}
                .data=${{
                  existing: pr.existing,
                  pull_request: pr.pull_request,
                }}
              ></pr-card>
            `;
          });

  const changesRequestedPct = jobsSummary?.total_with_pr
    ? ((jobsSummary.changes_requested / jobsSummary.total_with_pr) * 100).toFixed(1)
    : null;

  const summaryStats = jobsSummary ? [
    {
      key: "changes",
      label: "Changes requested",
      value: jobsSummary.changes_requested,
      sub: `${changesRequestedPct}% of ${jobsSummary.total_with_pr} open PRs`,
      copyText: `[changes requested] ${jobsSummary.changes_requested} (${changesRequestedPct}% of ${jobsSummary.total_with_pr} open PRs)`,
    },
    {
      key: "open",
      label: "Open pull requests",
      value: jobsSummary.total_with_pr,
      sub: "awaiting review or merge",
      copyText: `[open pull requests] ${jobsSummary.total_with_pr}`,
    },
  ] : null;

  const summarySection = summaryStats
    ? html`<stat-cards .stats=${summaryStats}></stat-cards>`
    : null;

  const errorSection = permissions.JOBS_PAGE_ERRORS && errorJobs.length > 0 ? html`
    <section class="jobs-page__errors">
      <h2>Pipeline errors</h2>
      <div style="display: flex; gap: 2rem; flex-direction: column;">
        ${errorJobs.map((job) => html`<error-card .job=${job} @resolve-error=${handleResolveError}></error-card>`)}
      </div>
    </section>
  ` : null;

  return html`
    <main>
      <div class="jobs-page__filters">
        <civ-select-state
          .selected=${stateCode}
          @state-change=${handleStateChange}
        ></civ-select-state>
        <label class="jobs-page__per-page">
          Per page
          <select @change=${handlePerPageChange}>
            ${PER_PAGE_OPTIONS.map(
              (n) => html`<option value=${n} ?selected=${n === perPage}>${n}</option>`
            )}
          </select>
        </label>
      </div>
      ${summarySection}
      ${errorSection}
      <section class="jobs-page__duplicate-jurisdictions">
        <div class="jobs-page__section-header">
          <h2>Pull requests - duplicate jurisdictions</h2>
          ${duplicateJurisdictions.length > 0 ? html`
            <button
              class="btn btn-sm destructive"
              @click=${handleCloseStaleDuplicates}
              ?disabled=${closingStale}
            >${closingStale ? "Closing…" : "Close stale"}</button>
          ` : null}
        </div>
        <div class="jobs-page__duplicate-list">
          ${duplicatePrList}
        </div>
      </section>
      <section>
        <h2>Open pull requests</h2>
        <div style="display: flex; gap: 2rem; flex-direction: column;">
          ${prList}
        </div>
        <div class="jobs-page__pagination">
          ${!pageLoading ? html`
            <a
              class="btn btn-sm"
              href="?page=${page - 1}"
              aria-disabled=${page <= 1}
              @click=${(e) => { e.preventDefault(); if (page > 1) goToPage(page - 1); }}
            >←</a>
            <nav class="jobs-page__page-numbers">
              ${getPageRange(page, totalPages).map((n) =>
                n === "..."
                  ? html`<span class="jobs-page__page-ellipsis">…</span>`
                  : html`<a
                      class="btn btn-sm jobs-page__page-btn${n === page ? " jobs-page__page-btn--active" : ""}"
                      href="?page=${n}"
                      @click=${(e) => { e.preventDefault(); goToPage(n); }}
                    >${n}</a>`
              )}
            </nav>
            <a
              class="btn btn-sm"
              href="?page=${page + 1}"
              aria-disabled=${page >= totalPages}
              @click=${(e) => { e.preventDefault(); if (page < totalPages) goToPage(page + 1); }}
            >→</a>
          ` : null}

          <label class="jobs-page__per-page">
            Per page
            <select @change=${handlePerPageChange}>
              ${PER_PAGE_OPTIONS.map(
                (n) => html`<option value=${n} ?selected=${n === perPage}>${n}</option>`
              )}
            </select>
          </label>
        </div>
      </section>
    </main>
  `;
}

customElements.define(
  "jobs-page",
  component(JobsPage, { useShadowDOM: false }),
);
export default JobsPage;
