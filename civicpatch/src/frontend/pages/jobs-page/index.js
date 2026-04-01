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

const API_URL = config.apiUrl;

function getStateFromUrl() {
  const val = new URLSearchParams(window.location.search).get("state");
  return val ? val.toLowerCase() : "";
}

function JobsPage() {
  const { permissions } = useAuth();
  const [defaultState, setDefaultState] = useLocalStorage("app:default-state", "", { ttl: PERSIST_FOREVER });
  const [stateCode, setStateCode] = useState(getStateFromUrl() || defaultState);
  const [jobsSummary, setJobsSummary] = useState(null);
  const [pullRequests, setPullRequests] = useState([]);
  const [pullRequestState, setPullRequestState] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!stateCode) return;

    setLoading(true);
    setError(null);

    fetchPullRequestsWithData(stateCode)
      .then((prResult) => {
        setPullRequests(prResult.data || []);
        setJobsSummary(prResult.summary || null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [stateCode]);

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
    window.history.pushState({}, "", `${window.location.pathname}?${params}`);
    setDefaultState(newState || "");
    setStateCode(newState);
  };

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
    <main class="jobs-page page-content">
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
          <h2 class="jobs-page__section-title jobs-page__section-title--primary">Open pull requests</h2>
          <div style="display: flex; gap: 2rem; flex-direction: column;">
            ${prList}
          </div>
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
