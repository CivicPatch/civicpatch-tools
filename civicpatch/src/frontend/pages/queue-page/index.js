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
import { Pagination } from "../../components/pagination/index.js";
import "../../components/pull-request-card/index.js";
import "../../components/stat-cards/index.js";
import "../../components/search-jurisdictions/select-state.js";

const DEFAULT_PER_PAGE = 10;
const PER_PAGE_OPTIONS = [10, 25, 50];

function getPageFromUrl() {
  const val = parseInt(new URLSearchParams(window.location.search).get("page"), 10);
  return isNaN(val) || val < 1 ? 1 : val;
}

function getPerPageFromUrl() {
  const val = parseInt(new URLSearchParams(window.location.search).get("per_page"), 10);
  return PER_PAGE_OPTIONS.includes(val) ? val : DEFAULT_PER_PAGE;
}

function setPageParamsInUrl(page, perPage) {
  const params = new URLSearchParams(window.location.search);
  params.set("page", page);
  params.set("per_page", perPage);
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

const API_URL = config.apiUrl;

function getStateFromUrl() {
  const val = new URLSearchParams(window.location.search).get("state");
  return val ? val.toLowerCase() : "";
}

function QueuePage() {
  const { permissions } = useAuth();
  const [defaultState, setDefaultState] = useLocalStorage("app:default-state", "", { ttl: PERSIST_FOREVER });
  const [stateCode, setStateCode] = useState(getStateFromUrl() || defaultState);
  const [queueSummary, setQueueSummary] = useState(null);
  const [pullRequests, setPullRequests] = useState([]);
  const [pullRequestState, setPullRequestState] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(getPageFromUrl());
  const [perPage, setPerPage] = useState(getPerPageFromUrl());
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
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

    fetchPullRequestsWithData(stateCode, page, perPage)
      .then((prResult) => {
        setPullRequests(prResult.data || []);
        setQueueSummary(prResult.summary || null);
        setTotalPages(prResult.total_pages || 1);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [stateCode, page, perPage]);

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
    params.set("page", 1);
    params.set("per_page", perPage);
    window.history.pushState({}, "", `${window.location.pathname}?${params}`);
    setDefaultState(newState || "");
    setStateCode(newState);
    setPage(1);
  };

  const handlePageChange = (newPage) => {
    setPageParamsInUrl(newPage, perPage);
    setPage(newPage);
  };

  const handlePerPageChange = (e) => {
    const newPerPage = parseInt(e.target.value, 10);
    setPageParamsInUrl(1, newPerPage);
    setPerPage(newPerPage);
    setPage(1);
  };

  const withIssuesPct = queueSummary?.total_with_pr
    ? ((queueSummary.with_issues / queueSummary.total_with_pr) * 100).toFixed(1)
    : null;

  const summaryStats = queueSummary ? [
    {
      key: "with_issues",
      label: "With issues",
      value: queueSummary.with_issues,
      sub: `${withIssuesPct}% of ${queueSummary.total_with_pr} open PRs`,
      copyText: `[with issues] ${queueSummary.with_issues} (${withIssuesPct}% of ${queueSummary.total_with_pr} open PRs)`,
    },
    {
      key: "open",
      label: "Open pull requests",
      value: queueSummary.total_with_pr,
      sub: "awaiting review or merge",
      copyText: `[open pull requests] ${queueSummary.total_with_pr}`,
    },
  ] : null;

  const summarySection = summaryStats
    ? html`<stat-cards .stats=${summaryStats}></stat-cards>`
    : null;

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
    <main class="queue-page page-content">
      <div class="queue-page__filters">
        <civ-select-state
          .selected=${stateCode}
          @state-change=${handleStateChange}
        ></civ-select-state>
        ${permissions.QUEUE_PAGE_ERRORS ? html`
          <div class="queue-page__filters-right">
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
      ${!stateCode ? html`<p class="queue-page__select-state-prompt">Select a state to get started.</p>` : html`
        ${summarySection}
        <section>
          <div class="queue-page__top-controls">
            <div class="queue-page__pagination queue-page__pagination--top">
              ${Pagination({ page, totalPages, onPrevious: () => handlePageChange(page - 1), onNext: () => handlePageChange(page + 1), onGoToPage: handlePageChange })}
            </div>
            <div class="queue-page__per-page">
              <label>Per page
                <select @change=${handlePerPageChange}>
                  ${PER_PAGE_OPTIONS.map((n) => html`<option value=${n} ?selected=${n === perPage}>${n}</option>`)}
                </select>
              </label>
            </div>
          </div>
          <div style="display: flex; gap: 2rem; flex-direction: column;">
            ${prList}
          </div>
          <div class="queue-page__pagination">
            ${Pagination({ page, totalPages, onPrevious: () => handlePageChange(page - 1), onNext: () => handlePageChange(page + 1), onGoToPage: handlePageChange })}
          </div>
        </section>
      `}
    </main>
  `;
}

customElements.define(
  "queue-page",
  component(QueuePage, { useShadowDOM: false }),
);
export default QueuePage;
