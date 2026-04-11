import "./queue-page.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { config } from "../../assets/config.js";
import {
  fetchPullRequestsWithData,
  fetchActiveJobs,
  saveAndMerge,
  closePullRequest,
} from "../../api.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import "../../components/search-jurisdictions/select-state.js";
import "../../components/publish-log/index.js";
import "./queue-summary/index.js";
import "./active-jobs/index.js";
import "./pr-list/index.js";

const API_URL = config.apiUrl;

function getIntParam(key, fallback, allowed = null) {
  const val = parseInt(new URLSearchParams(window.location.search).get(key), 10);
  if (isNaN(val) || val < 1) return fallback;
  if (allowed && !allowed.includes(val)) return fallback;
  return val;
}

function getStateFromUrl() {
  const val = new URLSearchParams(window.location.search).get("state");
  return val ? val.toLowerCase() : "";
}

function getViewFromUrl() {
  const val = new URLSearchParams(window.location.search).get("view");
  return val === "detail" ? "detail" : val === "quick" ? "quick" : null;
}

function setPrParamsInUrl(page, perPage) {
  const params = new URLSearchParams(window.location.search);
  params.set("pr_page", page);
  params.set("pr_per_page", perPage);
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function setAjParamsInUrl(page, perPage) {
  const params = new URLSearchParams(window.location.search);
  params.set("aj_page", page);
  params.set("aj_per_page", perPage);
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function QueuePage() {
  const { permissions } = useAuth();
  const [defaultState, setDefaultState] = useLocalStorage("app:default-state", "", { ttl: PERSIST_FOREVER });
  const [defaultView, setDefaultView] = useLocalStorage("app:queue-view", "quick", { ttl: PERSIST_FOREVER });
  const [stateCode, setStateCode] = useState(getStateFromUrl() || defaultState);
  const [queueSummary, setQueueSummary] = useState(null);
  const [pullRequests, setPullRequests] = useState([]);
  const [pullRequestState, setPullRequestState] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(getIntParam("pr_page", 1));
  const [perPage, setPerPage] = useState(getIntParam("pr_per_page", 10, [10, 25, 50]));
  const [totalPages, setTotalPages] = useState(1);
  const [viewMode, setViewMode] = useState(getViewFromUrl() || defaultView);
  const [activeJobs, setActiveJobs] = useState([]);
  const [activeJobsPage, setActiveJobsPage] = useState(getIntParam("aj_page", 1));
  const [activeJobsTotalPages, setActiveJobsTotalPages] = useState(1);
  const [activeJobsPerPage, setActiveJobsPerPage] = useState(getIntParam("aj_per_page", 25, [10, 25, 50]));

  useEffect(() => {
    const onPopState = () => {
      setPage(getIntParam("pr_page", 1));
      setPerPage(getIntParam("pr_per_page", 10, [10, 25, 50]));
      setActiveJobsPage(getIntParam("aj_page", 1));
      setActiveJobsPerPage(getIntParam("aj_per_page", 25, [10, 25, 50]));
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
      .then((result) => {
        setPullRequests(result.data || []);
        setQueueSummary(result.summary || null);
        setTotalPages(result.total_pages || 1);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [stateCode, page, perPage, viewMode]);

  useEffect(() => {
    fetchActiveJobs(stateCode || undefined, activeJobsPage, activeJobsPerPage)
      .then((result) => {
        setActiveJobs(result.data || []);
        setActiveJobsTotalPages(result.total_pages || 1);
      })
      .catch(() => setActiveJobs([]));
  }, [stateCode, activeJobsPage, activeJobsPerPage]);

  const handleMerge = async (event) => {
    const { pullRequestNumber, request_id, jurisdiction_ocdid } = event.detail;
    try {
      setPullRequestState(prev => ({ ...prev, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_MERGE } }));
      await saveAndMerge(pullRequestNumber, request_id, jurisdiction_ocdid, null);
      setPullRequestState(prev => ({ ...prev, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.MERGED } }));
    } catch (err) {
      setPullRequestState(prev => ({ ...prev, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.ERROR, error: err } }));
    }
  };

  const handleClose = async (event) => {
    const { pullRequestNumber, request_id } = event.detail;
    try {
      setPullRequestState(prev => ({ ...prev, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_CLOSE } }));
      await closePullRequest(request_id, pullRequestNumber);
      setPullRequestState(prev => ({ ...prev, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.CLOSED } }));
    } catch (err) {
      setPullRequestState(prev => ({ ...prev, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.ERROR, error: err } }));
    }
  };

  const handleViewChange = (newView) => {
    const params = new URLSearchParams(window.location.search);
    params.set("view", newView);
    window.history.pushState({}, "", `${window.location.pathname}?${params}`);
    setDefaultView(newView);
    setViewMode(newView);
  };

  const handleStateChange = (e) => {
    const newState = e.detail.state;
    const params = new URLSearchParams(window.location.search);
    params.set("state", newState);
    params.set("pr_page", 1);
    params.set("pr_per_page", perPage);
    params.set("aj_page", 1);
    params.set("aj_per_page", 25);
    window.history.pushState({}, "", `${window.location.pathname}?${params}`);
    setDefaultState(newState || "");
    setStateCode(newState);
    setPage(1);
    setActiveJobsPage(1);
    setActiveJobsPerPage(25);
  };

  const handlePageChange = (newPage) => {
    setPrParamsInUrl(newPage, perPage);
    setPage(newPage);
  };

  const handlePerPageChange = (e) => {
    const newPerPage = parseInt(e.target.value, 10);
    setPrParamsInUrl(1, newPerPage);
    setPerPage(newPerPage);
    setPage(1);
  };

  const publishLogEntries = Object.entries(pullRequestState)
    .filter(([, s]) => [PULL_REQUEST_STATUS.LOADING_MERGE, PULL_REQUEST_STATUS.MERGED, PULL_REQUEST_STATUS.ERROR].includes(s.status))
    .map(([prNumber, s]) => {
      const pr = pullRequests.find(p => p.pr.number === parseInt(prNumber, 10));
      return {
        pullRequestNumber: parseInt(prNumber, 10),
        jurisdictionName: pr?.jurisdiction?.name || `#${prNumber}`,
        status: s.status,
      };
    });

  return html`
    <main class="queue-page page-content">
      <div class="queue-page__filters">
        <civ-select-state
          .selected=${stateCode}
          @state-change=${handleStateChange}
        ></civ-select-state>
        ${permissions.QUEUE_PAGE_ERRORS ? html`
          <div class="queue-page__filters-right">
            <a class="btn btn-sm" href="${API_URL}/api/v1/requests/people-export.csv?state=${stateCode}" download>Export people</a>
            <a class="btn btn-sm" href="${API_URL}/api/v1/requests/export.csv?state=${stateCode}" download>Export queue</a>
          </div>
        ` : null}
      </div>

      ${!stateCode ? html`<p class="queue-page__select-state-prompt">Select a state to get started.</p>` : null}

      ${stateCode ? html`
        ${queueSummary ? html`<queue-summary .summary=${queueSummary}></queue-summary>` : null}
        <queue-active-jobs
          .jobs=${activeJobs}
          .page=${activeJobsPage}
          .totalPages=${activeJobsTotalPages}
          .perPage=${activeJobsPerPage}
          .onPageChange=${(p) => { setAjParamsInUrl(p, activeJobsPerPage); setActiveJobsPage(p); }}
          .onPerPageChange=${(e) => { const n = parseInt(e.target.value, 10); setAjParamsInUrl(1, n); setActiveJobsPerPage(n); setActiveJobsPage(1); }}
        ></queue-active-jobs>
        <queue-pr-list
          .pullRequests=${pullRequests}
          .pullRequestState=${pullRequestState}
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
