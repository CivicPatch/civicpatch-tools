import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { config } from "../../assets/config.js";
import {
  fetchPullRequestsWithData,
  saveAndMerge,
  closePullRequest,
} from "../../api.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import "../../components/pull-request-card/index.js";
import "../../components/stat-cards/index.js";
import "../../components/search-jurisdictions/select-state.js";
import { Pagination } from "../../components/pagination/index.js";

const API_URL = config.apiUrl;

const DEFAULT_PER_PAGE = 20;
const PER_PAGE_OPTIONS = [10, 20, 50, 100];

function getPrsPageFromUrl() {
  const val = parseInt(new URLSearchParams(window.location.search).get("prs_page"), 10);
  return isNaN(val) || val < 1 ? 1 : val;
}

function getStateFromUrl() {
  const val = new URLSearchParams(window.location.search).get("state");
  return val ? val.toLowerCase() : "";
}

function getPrsPerPageFromUrl() {
  const val = parseInt(new URLSearchParams(window.location.search).get("prs_per_page"), 10);
  return PER_PAGE_OPTIONS.includes(val) ? val : DEFAULT_PER_PAGE;
}

function setPrsPageInUrl(page) {
  const params = new URLSearchParams(window.location.search);
  params.set("prs_page", page);
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}


function JobsPage() {
  const { permissions } = useAuth();
  const [defaultState, setDefaultState] = useLocalStorage("app:default-state", "", { ttl: PERSIST_FOREVER });
  const [stateCode, setStateCode] = useState(getStateFromUrl() || defaultState);
  const [page, setPage] = useState(getPrsPageFromUrl());
  const [perPage, setPerPage] = useState(getPrsPerPageFromUrl());
  const [total, setTotal] = useState(0);
  const [jobsSummary, setJobsSummary] = useState(null);
  const [pullRequests, setPullRequests] = useState([]);
  const [pullRequestState, setPullRequestState] = useState({});
  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [error, setError] = useState(null);

  const [openSections, setOpenSections] = useLocalStorage(
    "jobs-page:open-sections",
    { prs: true },
    { ttl: PERSIST_FOREVER },
  );
  const toggleSection = (key) => setOpenSections({ ...openSections, [key]: !openSections[key] });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (stateCode) {
      if (!params.get("prs_page")) params.set("prs_page", page);
      if (!params.get("prs_per_page")) params.set("prs_per_page", perPage);
      window.history.replaceState({}, "", `${window.location.pathname}?${params}`);
    }
    const onPopState = () => {
      setPage(getPrsPageFromUrl());
      setPerPage(getPrsPerPageFromUrl());
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (!stateCode || !openSections.prs) return;

    setLoading(true);
    setError(null);

    fetchPullRequestsWithData(page, perPage, stateCode)
      .then((prResult) => {
        setPullRequests(prResult.data || []);
        setTotal(prResult.total || 0);
        setJobsSummary(prResult.summary || null);
      })
      .catch((err) => setError(err.message))
      .finally(() => { setLoading(false); setPageLoading(false); });
  }, [page, perPage, stateCode, openSections.prs]);

  const handleMerge = async (event) => {
    const { pullRequestNumber, request_id, jurisdiction_ocdid } = event.detail;
    try {
      setPullRequestState({ ...pullRequestState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_MERGE } });
      await saveAndMerge(pullRequestNumber, request_id, jurisdiction_ocdid, null);
      setPullRequestState({ ...pullRequestState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.MERGED } });
    } catch (error) {
      setPullRequestState({ ...pullRequestState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.ERROR, error } });
    }
  };

  const handleClose = async (event) => {
    const { pullRequestNumber, request_id } = event.detail;
    try {
      setPullRequestState({ ...pullRequestState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_CLOSE } });
      await closePullRequest(request_id, pullRequestNumber);
      setPullRequestState({ ...pullRequestState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.CLOSED } });
    } catch (error) {
      setPullRequestState({ ...pullRequestState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.ERROR, error } });
    }
  };

  const handleStateChange = (e) => {
    const newState = e.detail.state;
    const params = new URLSearchParams(window.location.search);
    params.set("state", newState);
    params.set("prs_page", 1);
    window.history.pushState({}, "", `${window.location.pathname}?${params}`);
    setDefaultState(newState || "");
    setStateCode(newState);
    setPage(1);
  };

  const goToPage = (newPage) => {
    setPageLoading(true);
    setPrsPageInUrl(newPage);
    setPage(newPage);
  };

  const handlePerPageChange = (e) => {
    const newPerPage = parseInt(e.target.value, 10);
    const params = new URLSearchParams(window.location.search);
    params.set("prs_per_page", newPerPage);
    params.set("prs_page", 1);
    window.history.pushState({}, "", `${window.location.pathname}?${params}`);
    setPerPage(newPerPage);
    setPage(1);
  };

  const totalPages = Math.ceil(total / perPage);

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

  const paginationControls = !pageLoading ? Pagination({
    page,
    totalPages,
    onPrevious: () => goToPage(page - 1),
    onNext: () => goToPage(page + 1),
    onGoToPage: goToPage,
    hrefForPage: (n) => `?prs_page=${n}`,
  }) : null;

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
            >Export queue</a>
          </div>
        ` : null}
      </div>
      ${!stateCode ? html`<p class="jobs-page__select-state-prompt">Select a state to get started.</p>` : html`
      ${summarySection}
      <section>
        <div class="jobs-page__section-header" @click=${() => toggleSection('prs')}>
          <h2 class="jobs-page__section-title jobs-page__section-title--primary">Open pull requests <span class="jobs-page__section-count">${total}</span></h2>
          <i class="fa-solid fa-chevron-down jobs-page__section-toggle${openSections.prs ? ' jobs-page__section-toggle--open' : ''}"></i>
        </div>
        ${openSections.prs ? html`
          <div class="jobs-page__top-controls">
            <div class="jobs-page__pagination">
              ${paginationControls}
            </div>
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
