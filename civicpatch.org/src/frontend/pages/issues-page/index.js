import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { useSummary } from "../../hooks/useSummary.js";
import {
  fetchJobsWithErrors,
  fetchJobIssues,
  resolveReviewIssue,
  fetchDuplicatePrJurisdictionJobs,
  fetchPullRequests,
  closeStaleDuplicatePrs,
  resolveJob,
  resumeJob,
  saveAndMerge,
  closePullRequest,
} from "../../api.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import "../../components/pull-request-card/index.js";
import "../queue-page/error-card/index.js";
import { Pagination } from "../../components/pagination/index.js";
import "./issues-page.css";

const DEFAULT_ISSUES_PER_PAGE = 20;
const ISSUES_PER_PAGE_OPTIONS = [10, 20, 50, 100];

const KNOWN_ISSUE_TYPES = [
  { value: "unrecognized_role", label: "Unrecognized role" },
  { value: "dead_url", label: "Dead URL" },
  { value: "excluded_person", label: "Excluded person" },
];

function getIssuesPageFromUrl() {
  const val = parseInt(new URLSearchParams(window.location.search).get("issues_page"), 10);
  return isNaN(val) || val < 1 ? 1 : val;
}

function getIssuesPerPageFromUrl() {
  const val = parseInt(new URLSearchParams(window.location.search).get("issues_per_page"), 10);
  return ISSUES_PER_PAGE_OPTIONS.includes(val) ? val : DEFAULT_ISSUES_PER_PAGE;
}

function getIssuesTagsFromUrl() {
  const val = new URLSearchParams(window.location.search).get("issues_tags");
  return val ? val.split(",").filter(Boolean) : [];
}

function getIssuesSortDescFromUrl() {
  return new URLSearchParams(window.location.search).get("issues_sort") !== "asc";
}

function setIssuesPageInUrl(page) {
  const params = new URLSearchParams(window.location.search);
  params.set("issues_page", page);
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function setIssuesParamsInUrl(page, perPage, tags, sortDesc) {
  const params = new URLSearchParams(window.location.search);
  params.set("issues_page", page);
  params.set("issues_per_page", perPage);
  if (tags && tags.length) params.set("issues_tags", tags.join(","));
  else params.delete("issues_tags");
  params.set("issues_sort", sortDesc ? "desc" : "asc");
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}


function getIssueDetail(issueType, issueKey, data) {
  if (!data) return issueKey || "";
  if (issueType === "unrecognized_role") {
    const names = (data.person_names || []).join(", ");
    return names ? `${issueKey} — ${names}` : issueKey;
  }
  if (issueType === "dead_url") return data.url || issueKey;
  if (issueType === "excluded_person") return data.name || issueKey;
  return issueKey;
}

function formatIssueType(issueType) {
  return KNOWN_ISSUE_TYPES.find((t) => t.value === issueType)?.label ?? issueType;
}

function formatDate(isoString) {
  if (!isoString) return "";
  return new Date(isoString).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function IssuesPage() {
  const { permissions } = useAuth();
  const summary = useSummary(true);

  // Errors section
  const [errorJobs, setErrorJobs] = useState([]);
  const [errorsLoading, setErrorsLoading] = useState(false);

  // Issues section
  const [issues, setIssues] = useState([]);
  const [issuesTotal, setIssuesTotal] = useState(0);
  const [issuesPage, setIssuesPage] = useState(getIssuesPageFromUrl());
  const [issuesPerPage, setIssuesPerPage] = useState(getIssuesPerPageFromUrl());
  const [issuesTagFilter, setIssuesTagFilter] = useState(getIssuesTagsFromUrl());
  const [issuesSortDesc, setIssuesSortDesc] = useState(getIssuesSortDescFromUrl());
  const [issuesLoading, setIssuesLoading] = useState(false);
  const [issuesPageLoading, setIssuesPageLoading] = useState(false);

  // Duplicates section
  const [duplicateJurisdictions, setDuplicateJurisdictions] = useState([]);
  const [duplicateJurisdictionPRs, setDuplicateJurisdictionPRs] = useState({});
  const [openJurisdictions, setOpenJurisdictions] = useState({});
  const [closingStale, setClosingStale] = useState(false);
  const [prState, setPrState] = useState({});

  const [openSections, setOpenSections] = useLocalStorage(
    "issues-page:open-sections",
    { errors: true, issues: true, duplicates: true },
    { ttl: PERSIST_FOREVER },
  );
  const toggleSection = (key) => setOpenSections({ ...openSections, [key]: !openSections[key] });

  // Sync URL → state on browser back/forward
  useEffect(() => {
    const onPopState = () => {
      setIssuesPage(getIssuesPageFromUrl());
      setIssuesPerPage(getIssuesPerPageFromUrl());
      setIssuesTagFilter(getIssuesTagsFromUrl());
      setIssuesSortDesc(getIssuesSortDescFromUrl());
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  // Errors — lazy, only when section is open
  useEffect(() => {
    if (!openSections.errors) return;
    setErrorsLoading(true);
    fetchJobsWithErrors()
      .then((r) => setErrorJobs(r.data || []))
      .catch(console.error)
      .finally(() => setErrorsLoading(false));
  }, [openSections.errors]);

  // Issues — lazy, refetch on any filter/page/sort change
  useEffect(() => {
    if (!openSections.issues) return;
    setIssuesLoading(true);
    fetchJobIssues(issuesTagFilter, issuesPage, issuesPerPage, issuesSortDesc ? "desc" : "asc")
      .then((r) => { setIssues(r.data || []); setIssuesTotal(r.total || 0); })
      .catch(console.error)
      .finally(() => { setIssuesLoading(false); setIssuesPageLoading(false); });
  }, [openSections.issues, issuesPage, issuesPerPage, issuesTagFilter, issuesSortDesc]);

  // Duplicates — lazy, only when section is open
  useEffect(() => {
    if (!openSections.duplicates) return;
    fetchDuplicatePrJurisdictionJobs()
      .then((r) => setDuplicateJurisdictions(r.data || []))
      .catch(console.error);
  }, [openSections.duplicates]);

  const handleResolveError = async (event) => {
    const { job } = event.detail;
    try {
      await resolveJob(job.request_id);
      setErrorJobs(errorJobs.filter((j) => j.request_id !== job.request_id));
    } catch (err) {
      console.error("Failed to resolve job:", err);
    }
  };

  const handleResumeJob = async (event) => {
    const { job } = event.detail;
    try {
      await resumeJob(job.request_id);
      setErrorJobs(errorJobs.filter((j) => j.request_id !== job.request_id));
    } catch (err) {
      console.error("Failed to resume job:", err);
    }
  };

  const handleToggleTag = (tag) => {
    const next = issuesTagFilter.includes(tag)
      ? issuesTagFilter.filter((t) => t !== tag)
      : [...issuesTagFilter, tag];
    setIssuesTagFilter(next);
    setIssuesPage(1);
    setIssuesParamsInUrl(1, issuesPerPage, next, issuesSortDesc);
  };

  const handleToggleSort = () => {
    const next = !issuesSortDesc;
    setIssuesSortDesc(next);
    setIssuesPage(1);
    setIssuesParamsInUrl(1, issuesPerPage, issuesTagFilter, next);
  };

  const goToIssuesPage = (newPage) => {
    setIssuesPageLoading(true);
    setIssuesPageInUrl(newPage);
    setIssuesPage(newPage);
  };

  const handleIssuesPerPageChange = (e) => {
    const newPerPage = parseInt(e.target.value, 10);
    setIssuesPerPage(newPerPage);
    setIssuesPage(1);
    setIssuesParamsInUrl(1, newPerPage, issuesTagFilter, issuesSortDesc);
  };

  const handleResolveIssue = async (issue) => {
    try {
      await resolveReviewIssue(issue.id);
      setIssues(issues.filter((i) => i.id !== issue.id));
      setIssuesTotal((t) => t - 1);
    } catch (err) {
      console.error("Failed to resolve issue:", err);
    }
  };

  const loadJurisdictionPRs = async (ocdid) => {
    setOpenJurisdictions((prev) => ({ ...prev, [ocdid]: !prev[ocdid] }));
    if (!duplicateJurisdictionPRs[ocdid]) {
      const result = await fetchPullRequests(ocdid);
      setDuplicateJurisdictionPRs((prev) => ({ ...prev, [ocdid]: result.data || [] }));
    }
  };

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

  const handleDuplicateMerge = async (event) => {
    const { pullRequestNumber, request_id, jurisdiction_ocdid } = event.detail;
    try {
      setPrState({ ...prState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_MERGE } });
      await saveAndMerge(pullRequestNumber, request_id, jurisdiction_ocdid, null);
      setPrState({ ...prState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.MERGED } });
    } catch (err) {
      setPrState({ ...prState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.ERROR, error: err } });
    }
  };

  const handleDuplicateClose = async (event) => {
    const { pullRequestNumber, request_id } = event.detail;
    try {
      setPrState({ ...prState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_CLOSE } });
      await closePullRequest(request_id, pullRequestNumber);
      setPrState({ ...prState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.CLOSED } });
    } catch (err) {
      setPrState({ ...prState, [pullRequestNumber]: { status: PULL_REQUEST_STATUS.ERROR, error: err } });
    }
  };

  const issuesTotalPages = Math.ceil(issuesTotal / issuesPerPage);

  // --- Render helpers ---

  const issuesPaginationControls = !issuesPageLoading ? Pagination({
    page: issuesPage,
    totalPages: issuesTotalPages,
    onPrevious: () => goToIssuesPage(issuesPage - 1),
    onNext: () => goToIssuesPage(issuesPage + 1),
    onGoToPage: goToIssuesPage,
    hrefForPage: (n) => `?issues_page=${n}`,
  }) : null;

  const tagChips = KNOWN_ISSUE_TYPES.map(({ value, label }) => {
    const active = issuesTagFilter.includes(value);
    return html`
      <button
        class="issues-page__issue-tag${active ? " issues-page__issue-tag--active" : ""}"
        @click=${() => handleToggleTag(value)}
      >${label}${active ? html` <span class="issues-page__issue-tag-x">×</span>` : ""}</button>
    `;
  });

  const issuesSection = html`
    <section class="issues-page__section">
      <div class="issues-page__section-header" @click=${() => toggleSection("issues")}>
        <h2 class="issues-page__section-title issues-page__section-title--info">Issues <span class="issues-page__section-count">${issuesTotal || summary?.issues_total || ""}</span></h2>
        <i class="fa-solid fa-chevron-down btn-icon${openSections.issues ? " btn-icon--rotated" : ""}"></i>
      </div>
      ${openSections.issues ? html`
        <div class="issues-page__issues-filters">
          <div class="issues-page__issue-tags">${tagChips}</div>
          <button
            class="btn btn-sm issues-page__sort-btn"
            @click=${handleToggleSort}
          >${issuesSortDesc ? "Newest ↓" : "Oldest ↑"}</button>
        </div>
        ${issuesLoading ? html`<div>Loading…</div>` : html`
          <table class="issues-page__issues-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Detail</th>
                <th>Jurisdiction</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${issues.length === 0
                ? html`<tr><td colspan="5">No issues found.</td></tr>`
                : issues.map((ev) => html`
                  <tr>
                    <td><span class="issues-page__issue-type-chip issues-page__issue-type-chip--${ev.issue_type.replace(/_/g, "-")}">${formatIssueType(ev.issue_type)}</span></td>
                    <td class="issues-page__issue-detail">${getIssueDetail(ev.issue_type, ev.issue_key, ev.data)}</td>
                    <td>
                      ${ev.jurisdiction_ocdid
                        ? html`<a href="/${ev.jurisdiction_path}" target="_blank">${ev.jurisdiction_name || ev.jurisdiction_ocdid}</a>`
                        : "—"}
                    </td>
                    <td class="issues-page__issue-date">${formatDate(ev.created_at)}</td>
                    <td>
                      ${ev.issue_type === "unrecognized_role" || ev.issue_type === "dead_url"
                        ? html`<button class="btn btn-sm" @click=${() => handleResolveIssue(ev)}>Resolve</button>`
                        : ""}
                    </td>
                  </tr>
                `)
              }
            </tbody>
          </table>
          <div class="issues-page__top-controls">
            <div class="issues-page__pagination">
              ${issuesPaginationControls}
            </div>
            <label class="issues-page__per-page">
              Per page
              <select @change=${handleIssuesPerPageChange}>
                ${ISSUES_PER_PAGE_OPTIONS.map(
                  (n) => html`<option value=${n} ?selected=${n === issuesPerPage}>${n}</option>`
                )}
              </select>
            </label>
          </div>
        `}
      ` : null}
    </section>
  `;

  const errorsCount = openSections.errors ? errorJobs.length : (summary?.pipeline_errors ?? "");
  const errorsSection = html`
    <section class="issues-page__section">
      ${errorsCount === 0 && !errorsLoading ? html`
        <h2 class="issues-page__section-title issues-page__section-title--error">Pipeline errors <span class="issues-page__section-count">0</span></h2>
      ` : html`
        <div class="issues-page__section-header" @click=${() => toggleSection("errors")}>
          <h2 class="issues-page__section-title issues-page__section-title--error">Pipeline errors <span class="issues-page__section-count">${errorsCount}</span></h2>
          <i class="fa-solid fa-chevron-down btn-icon${openSections.errors ? " btn-icon--rotated" : ""}"></i>
        </div>
        ${openSections.errors ? html`
          ${errorsLoading
            ? html`<div>Loading…</div>`
            : html`<div style="display:flex;gap:2rem;flex-direction:column;">${errorJobs.map((job) => html`<error-card .job=${job} @resolve-error=${handleResolveError} @resume-job=${handleResumeJob}></error-card>`)}</div>`
          }
        ` : null}
      `}
    </section>
  `;

  const duplicatePrList = duplicateJurisdictions.map((ocdid) => {
    const isOpen = openJurisdictions[ocdid];
    return html`
      <div class="issues-page__duplicate-item">
        <button
          class="issues-page__duplicate-item-header${isOpen ? " issues-page__duplicate-item-header--open" : ""}"
          @click=${() => loadJurisdictionPRs(ocdid)}
        >
          <span>${ocdid}</span>
          <i class="fa-solid fa-chevron-down btn-icon${isOpen ? " btn-icon--rotated" : ""}"></i>
        </button>
        ${isOpen ? html`
          <div class="issues-page__duplicate-item-body">
            ${(duplicateJurisdictionPRs[ocdid] || []).map((pr) => {
              const pullRequestNumber = pr.pr.number;
              return html`
                <pr-card
                  @onMerge=${handleDuplicateMerge}
                  @onClose=${handleDuplicateClose}
                  .entry=${pr}
                  .state=${prState[pullRequestNumber]}
                ></pr-card>
              `;
            })}
          </div>
        ` : null}
      </div>
    `;
  });

  const duplicatesCount = openSections.duplicates ? duplicateJurisdictions.length : (summary?.duplicate_jurisdictions ?? "");
  const duplicatesSection = html`
    <section class="issues-page__section">
      ${duplicatesCount === 0 ? html`
        <h2 class="issues-page__section-title issues-page__section-title--warning">Duplicate jurisdictions <span class="issues-page__section-count">0</span></h2>
      ` : html`
        <div class="issues-page__section-header" @click=${() => toggleSection("duplicates")}>
          <h2 class="issues-page__section-title issues-page__section-title--warning">Duplicate jurisdictions <span class="issues-page__section-count">${duplicatesCount}</span></h2>
          <i class="fa-solid fa-chevron-down btn-icon${openSections.duplicates ? " btn-icon--rotated" : ""}"></i>
        </div>
        ${openSections.duplicates ? html`
          <button
            class="btn btn-sm destructive"
            @click=${handleCloseStaleDuplicates}
            ?disabled=${closingStale}
          >${closingStale ? "Closing…" : "Close stale"}</button>
          <div class="issues-page__duplicate-list">${duplicatePrList}</div>
        ` : null}
      `}
    </section>
  `;

  return html`
    <main class="issues-page page-content">
      ${errorsSection}
      ${issuesSection}
      ${duplicatesSection}
    </main>
  `;
}

customElements.define(
  "issues-page",
  component(IssuesPage, { useShadowDOM: false }),
);
export default IssuesPage;
