import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { config } from "../../assets/config.js";
import {
  fetchPullRequestsWithData,
  fetchJobsWithErrors,
  fetchUnrecognizedRoles,
  saveAndMerge,
  closePullRequest,
  resolveJob,
  fetchDuplicatePrJurisdictionJobs,
  fetchPullRequests,
  closeStaleDuplicatePrs,
} from "../../api.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import "../../components/pull-request-card/index.js";
import "./error-card/index.js";
import "../../components/stat-cards/index.js";
import "../../components/search-jurisdictions/select-state.js";

const API_URL = config.apiUrl;

const DEFAULT_PER_PAGE = 20;
const PER_PAGE_OPTIONS = [10, 20, 50, 100];

function getPageFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const page = parseInt(params.get("page"), 10);
  return isNaN(page) || page < 1 ? 1 : page;
}

function getStateFromUrl() {
  const val = new URLSearchParams(window.location.search).get("state");
  return val ? val.toLowerCase() : "";
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
  const [defaultState, setDefaultState] = useLocalStorage("app:default-state", "", { ttl: PERSIST_FOREVER });
  const [stateCode, setStateCode] = useState(getStateFromUrl() || defaultState);
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
  const [unrecognizedRoles, setUnrecognizedRoles] = useState([]);
  const [error, setError] = useState(null);
  const [perPage, setPerPage] = useState(getPerPageFromUrl());

  const [openSections, setOpenSections] = useLocalStorage(
    "jobs-page:open-sections",
    { errors: true, duplicates: true, prs: true, unrecognized: true },
    { ttl: PERSIST_FOREVER },
  );
  const toggleSection = (key) => setOpenSections({ ...openSections, [key]: !openSections[key] });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (stateCode) {
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
    if (!stateCode) return;

    setLoading(true);
    setError(null);

    Promise.all([
      fetchPullRequestsWithData(page, perPage, stateCode),
      fetchJobsWithErrors(stateCode),
      fetchDuplicatePrJurisdictionJobs(),
      fetchUnrecognizedRoles(stateCode),
    ])
      .then(([prResult, errResult, duplicatePrResult, unrecognizedResult]) => {
        setPullRequests(prResult.data || []);
        setTotal(prResult.total || 0);
        setErrorJobs(errResult.data || []);
        setJobsSummary(prResult.summary || null);
        // Expecting duplicatePrResult.jurisdiction_ocdids or .data as array of ocdids
        setDuplicateJurisdictions(
          duplicatePrResult.data || []
        );
        setUnrecognizedRoles(unrecognizedResult.data || []);
      })
      .catch((err) => setError(err.message))
      .finally(() => { setLoading(false); setPageLoading(false); });
  }, [page, perPage, stateCode]);

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
    setDefaultState(newState || "");
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
      const result = await fetchPullRequests(ocdid);
      setDuplicateJurisdictionPRs((prev) => ({ ...prev, [ocdid]: result.data || [] }));
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
              const pullRequestNumber = pr.pr.number;
              return html`
                <pr-card
                  @onMerge=${handleMerge}
                  @onClose=${handleClose}
                  .entry=${pr}
                  .state=${pullRequestState[pullRequestNumber]}
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
            const pullRequestNumber = pr.pr.number;
            return html`
              <pr-card
                @onMerge=${handleMerge}
                @onClose=${handleClose}
                .entry=${pr}
                .state=${pullRequestState[pullRequestNumber]}
              ></pr-card>
            `;
          });

  const withIssuesPct = jobsSummary?.total_with_pr
    ? ((jobsSummary.with_issues / jobsSummary.total_with_pr) * 100).toFixed(1)
    : null;

  const summaryStats = jobsSummary ? [
    {
      key: "with_issues",
      label: "With issues",
      value: jobsSummary.with_issues,
      sub: `${withIssuesPct}% of ${jobsSummary.total_with_pr} open PRs`,
      copyText: `[with issues] ${jobsSummary.with_issues} (${withIssuesPct}% of ${jobsSummary.total_with_pr} open PRs)`,
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

  const errorSection = permissions.JOBS_PAGE_ERRORS ? html`
    <section class="jobs-page__errors">
      ${errorJobs.length === 0 ? html`
        <h2 class="jobs-page__section-title jobs-page__section-title--error">Pipeline errors <span class="jobs-page__section-count">${errorJobs.length}</span></h2>
      ` : html`
        <div class="jobs-page__section-header" @click=${() => toggleSection('errors')}>
          <h2 class="jobs-page__section-title jobs-page__section-title--error">Pipeline errors <span class="jobs-page__section-count">${errorJobs.length}</span></h2>
          <span class="jobs-page__section-toggle${openSections.errors ? ' jobs-page__section-toggle--open' : ''}">▼</span>
        </div>
        ${openSections.errors ? html`
          <div style="display: flex; gap: 2rem; flex-direction: column;">
            ${errorJobs.map((job) => html`<error-card .job=${job} @resolve-error=${handleResolveError}></error-card>`)}
          </div>
        ` : null}
      `}
    </section>
  ` : null;

  const unrecognizedSection = permissions.JOBS_PAGE_ERRORS ? html`
    <section class="jobs-page__unrecognized-roles">
      ${unrecognizedRoles.length === 0 ? html`
        <h2 class="jobs-page__section-title jobs-page__section-title--warning">Unrecognized roles <span class="jobs-page__section-count">${unrecognizedRoles.length}</span></h2>
      ` : html`
        <div class="jobs-page__section-header" @click=${() => toggleSection('unrecognized')}>
          <h2 class="jobs-page__section-title jobs-page__section-title--warning">Unrecognized roles <span class="jobs-page__section-count">${unrecognizedRoles.length}</span></h2>
          <span class="jobs-page__section-toggle${openSections.unrecognized ? ' jobs-page__section-toggle--open' : ''}">▼</span>
        </div>
        ${openSections.unrecognized ? html`
          <table>
            <thead><tr><th>Role</th><th>Person</th><th>Status</th><th>Jurisdiction</th></tr></thead>
            <tbody>
              ${unrecognizedRoles.map((ur) => html`
                <tr>
                  <td><code>${ur.role}</code></td>
                  <td>${ur.person_name}</td>
                  <td>${ur.status}</td>
                  <td><a href="/jurisdictions?jurisdiction_ocdid=${ur.jurisdiction_ocdid}" target="_blank">${ur.jurisdiction_name || ur.jurisdiction_ocdid}</a></td>
                </tr>
              `)}
            </tbody>
          </table>
        ` : null}
      `}
    </section>
  ` : null;

  const paginationControls = !pageLoading ? html`
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
  ` : null;

  return html`
    <main class="jobs-page">
      <div class="jobs-page__filters">
        <civ-select-state
          .selected=${stateCode}
          @state-change=${handleStateChange}
        ></civ-select-state>
        ${permissions.JOBS_PAGE_ERRORS ? html`
          <div class="jobs-page__filters-right">
            <a
              class="btn btn-sm"
              href="${API_URL}/api/v1/requests/people-export.csv?state=${stateCode}"
              download
            >Export people</a>
            <a
              class="btn btn-sm"
              href="${API_URL}/api/v1/requests/export.csv?state=${stateCode}"
              download
            >Export open PRs</a>
          </div>
        ` : null}
      </div>
      ${!stateCode ? html`<p class="jobs-page__select-state-prompt">Select a state to get started.</p>` : html`
      ${summarySection}
      ${errorSection}
      ${unrecognizedSection}
      <section class="jobs-page__duplicate-jurisdictions">
        ${duplicateJurisdictions.length === 0 ? html`
          <h2 class="jobs-page__section-title jobs-page__section-title--warning">Duplicate jurisdictions <span class="jobs-page__section-count">${duplicateJurisdictions.length}</span></h2>
        ` : html`
          <div class="jobs-page__section-header" @click=${() => toggleSection('duplicates')}>
            <h2 class="jobs-page__section-title jobs-page__section-title--warning">Duplicate jurisdictions <span class="jobs-page__section-count">${duplicateJurisdictions.length}</span></h2>
            <div class="jobs-page__section-header-actions">
              <button
                class="btn btn-sm destructive"
                @click=${(e) => { e.stopPropagation(); handleCloseStaleDuplicates(); }}
                ?disabled=${closingStale}
              >${closingStale ? "Closing…" : "Close stale"}</button>
              <span class="jobs-page__section-toggle${openSections.duplicates ? ' jobs-page__section-toggle--open' : ''}">▼</span>
            </div>
          </div>
          ${openSections.duplicates ? html`
            <div class="jobs-page__duplicate-list">
              ${duplicatePrList}
            </div>
          ` : null}
        `}
      </section>
      <section>
        <div class="jobs-page__section-header" @click=${() => toggleSection('prs')}>
          <h2 class="jobs-page__section-title jobs-page__section-title--primary">Open pull requests <span class="jobs-page__section-count">${total}</span></h2>
          <span class="jobs-page__section-toggle${openSections.prs ? ' jobs-page__section-toggle--open' : ''}">▼</span>
        </div>
        ${openSections.prs ? html`
          <div class="jobs-page__pagination jobs-page__pagination--top">
            ${paginationControls}
            <label class="jobs-page__per-page">
              Per page
              <select @change=${handlePerPageChange}>
                ${PER_PAGE_OPTIONS.map(
                  (n) => html`<option value=${n} ?selected=${n === perPage}>${n}</option>`
                )}
              </select>
            </label>
          </div>
          <div style="display: flex; gap: 2rem; flex-direction: column;">
            ${prList}
          </div>
          <div class="jobs-page__pagination">
            ${paginationControls}
          </div>
        ` : null}
      </section>
      `}
    </main>
  `;
}

customElements.define(
  "jobs-page",
  component(JobsPage, { useShadowDOM: false }),
);
export default JobsPage;
