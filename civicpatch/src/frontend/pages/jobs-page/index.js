import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchPullRequestsWithData, mergePullRequest, closePullRequest } from "../../api.js";
import { PULL_REQUEST_STATUS } from "./pull-request-status.js";
import "./pull-request-card";
import "../../components/search-jurisdictions/select-state.js";

const DEFAULT_STATE = "TX";

function getPageFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const page = parseInt(params.get("page"), 10);
  return isNaN(page) || page < 1 ? 1 : page;
}

function getStateFromUrl() {
  return new URLSearchParams(window.location.search).get("state") || DEFAULT_STATE;
}

function setPageInUrl(page) {
  const params = new URLSearchParams(window.location.search);
  params.set("page", page);
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function JobsPage() {
  const [pullRequests, setPullRequests] = useState([]);
  const [pullRequestState, setPullRequestState] = useState({});
  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(getPageFromUrl());
  const [stateCode, setStateCode] = useState(getStateFromUrl());
  const [total, setTotal] = useState(0);
  const perPage = 10;

  useEffect(() => {
    const onPopState = () => setPage(getPageFromUrl());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);

    fetchPullRequestsWithData(page, perPage, stateCode.toLowerCase())
      .then((result) => {
        setPullRequests(result.data || []);
        setTotal(result.total || 0);
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
            const pullRequestNumber = pr.details.pull_request_number;
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

  return html`
    <main>
      <section>
        <div class="jobs-page__filters">
          <civ-select-state
            .selected=${stateCode}
            @state-change=${handleStateChange}
          ></civ-select-state>
        </div>
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
