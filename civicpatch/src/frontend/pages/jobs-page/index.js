import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { fetchPullRequestsWithData, fetchJobsWithErrors, mergePullRequest, closePullRequest, resolveJob } from "../../api.js";
import { pullRequestUrlToNumber } from "./pr-utils.js";
import { PULL_REQUEST_STATUS } from "./pull-request-status.js";
import "./pull-request-card";
import "./error-card/index.js";
import "../../components/search-jurisdictions/select-state.js";

const DEFAULT_STATE = "tx";

function getPageFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const page = parseInt(params.get("page"), 10);
  return isNaN(page) || page < 1 ? 1 : page;
}

function getStateFromUrl() {
  return (new URLSearchParams(window.location.search).get("state") || DEFAULT_STATE).toLowerCase();
}

function setPageInUrl(page) {
  const params = new URLSearchParams(window.location.search);
  params.set("page", page);
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function JobsPage() {
  const { permissions } = useAuth();
  const [pullRequests, setPullRequests] = useState([]);
  const [pullRequestState, setPullRequestState] = useState({});
  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(getPageFromUrl());
  const [stateCode, setStateCode] = useState(getStateFromUrl());
  const [total, setTotal] = useState(0);
  const [errorJobs, setErrorJobs] = useState([]);
  const [jobsSummary, setJobsSummary] = useState(null);
  const perPage = 20;

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (!params.get("state")) {
      params.set("state", stateCode);
      if (!params.get("page")) params.set("page", page);
      window.history.replaceState({}, "", `${window.location.pathname}?${params}`);
    }
    const onPopState = () => setPage(getPageFromUrl());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      fetchPullRequestsWithData(page, perPage, stateCode.toLowerCase()),
      fetchJobsWithErrors(stateCode.toLowerCase()),
    ])
      .then(([prResult, errResult]) => {
        setPullRequests(prResult.data || []);
        setTotal(prResult.total || 0);
        setErrorJobs(errResult.data || []);
        setJobsSummary(errResult.summary || null);
      })
      .catch((err) => setError(err.message))
      .finally(() => { setLoading(false); setPageLoading(false); });
  }, [page, stateCode]);

  const handleMerge = async (event) => {
    const pullRequestNumber = event.detail.pullRequestNumber;
    try {
      setPullRequestState({
        ...pullRequestState,
        [pullRequestNumber]: {
          status: PULL_REQUEST_STATUS.LOADING_MERGE,
        },
      });
      const response = await mergePullRequest(pullRequestNumber);
      if (response) {
        setPullRequestState({
          ...pullRequestState,
          [pullRequestNumber]: {
            status: PULL_REQUEST_STATUS.MERGED,
          },
        });
      }
    } catch (error) {
      setPullRequestState({
        ...pullRequestState,
        [pullRequestNumber]: {
          status: PULL_REQUEST_STATUS.ERROR,
          error,
        },
      });
    }
  };

  const handleClose = async (event) => {
    const pullRequestNumber = event.detail.pullRequestNumber;
    try {
      setPullRequestState({
        ...pullRequestState,
        [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_CLOSE },
      });
      await closePullRequest(pullRequestNumber);
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

  const totalPages = Math.ceil(total / perPage);

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

  const summarySection = jobsSummary ? html`
    <section class="jobs-page__summary">
      <div class="jobs-page__summary-grid">
        <div class="jobs-page__stat-card">
          <div class="jobs-page__stat-label">Changes requested</div>
          <div class="jobs-page__stat-main">${jobsSummary.changes_requested}</div>
          <div class="jobs-page__stat-sub">${changesRequestedPct}% of ${jobsSummary.total_with_pr} open PRs</div>
        </div>
        <div class="jobs-page__stat-card">
          <div class="jobs-page__stat-label">Open pull requests</div>
          <div class="jobs-page__stat-main">${jobsSummary.total_with_pr}</div>
          <div class="jobs-page__stat-sub">awaiting review or merge</div>
        </div>
      </div>
    </section>
  ` : null;

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
      </div>
      ${summarySection}
      ${errorSection}
      <section>
        <h2>Open pull requests</h2>
        <div style="display: flex; gap: 2rem; flex-direction: column;">
          ${prList}
        </div>
        <div
          style="margin-top:2rem; display:flex; gap:1rem; align-items:center;"
        >
          ${!pageLoading && page > 1
            ? html`<a
                class="btn"
                href="?page=${page - 1}"
                @click=${(e) => {
                  e.preventDefault();
                  goToPage(page - 1);
                }}
                >← Previous</a
              >`
            : null}

          ${!pageLoading ? html`<span class="jobs-page__page-counter">Page ${page} of ${totalPages}</span>` : null}

          ${!pageLoading && page < totalPages
            ? html`<a
                class="btn"
                href="?page=${page + 1}"
                @click=${(e) => {
                  e.preventDefault();
                  goToPage(page + 1);
                }}
                >Next →</a
              >`
            : null}
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
