import { html } from "lit-html";
import { keyed } from "lit-html/directives/keyed.js";
import { component, useState, useEffect } from "haunted";
import { useCsrf } from "../../hooks/use-csrf.js";
import { fetchPullRequestsWithData, mergePullRequest } from "../../api.js";
import "./pull-request-card";

function getPageFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const page = parseInt(params.get("page"), 10);
  return isNaN(page) || page < 1 ? 1 : page;
}

function setPageInUrl(page) {
  const params = new URLSearchParams(window.location.search);
  params.set("page", page);
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

export const PULL_REQUEST_STATUS = {
  LOADING: "loading",
  MERGED: "merged",
  ERROR: "error",
};

function JobsPage() {
  const [pullRequests, setPullRequests] = useState([]);
  const [pullRequestState, setPullRequestState] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(getPageFromUrl());
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

    fetchPullRequestsWithData(page, perPage)
      .then((result) => {
        setPullRequests(result.data || []);
        setTotal(result.total || 0);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [page]);

  const handleMerge = async (event) => {
    const pullRequestNumber = event.detail.pullRequestNumber;
    try {
      setPullRequestState({
        ...pullRequestState,
        [pullRequestNumber]: {
          status: PULL_REQUEST_STATUS.LOADING,
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

  const goToPage = (newPage) => {
    setPageInUrl(newPage);
    setPage(newPage);
  };

  const totalPages = Math.ceil(total / perPage);

  if (loading) return html`<div>Loading...</div>`;
  if (error) return html`<div>Error: ${error}</div>`;

  const prList =
    pullRequests.length === 0
      ? html`<p>No pull requests found.</p>`
      : pullRequests.map((pr) => {
          const pullRequestNumber = pr.details.pull_request_number;
          return html`
            <pr-card
              @onMerge=${handleMerge}
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
        <h2>Pull Requests</h2>
        <div style="display: flex; gap: 2rem; flex-direction: column;">
          ${prList}
        </div>
        <div
          style="margin-top:2rem; display:flex; gap:1rem; align-items:center;"
        >
          ${page > 1
            ? html`<a
                href="?page=${page - 1}"
                @click=${(e) => {
                  e.preventDefault();
                  if (page > 1) goToPage(page - 1);
                }}
                ?disabled=${page <= 1}
                >Previous</a
              >`
            : null}

          <span>Page ${page} of ${totalPages}</span>

          ${page < totalPages
            ? html` <a
                href="?page=${page + 1}"
                @click=${(e) => {
                  e.preventDefault();
                  if (page < totalPages) goToPage(page + 1);
                }}
                ?disabled=${page >= totalPages}
                >Next</a
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
