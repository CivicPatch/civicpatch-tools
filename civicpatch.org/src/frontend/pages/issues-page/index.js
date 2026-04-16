import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { useSummary } from "../../hooks/useSummary.js";
import {
  fetchJobIssues,
  fetchIssueDetails,
  resolveReviewIssue,
  dismissIssue,
  fetchDuplicatePrJurisdictionPipelineRuns,
  fetchPullRequests,
  closeStaleDuplicatePrs,
  saveAndMerge,
  closePullRequest,
} from "../../api.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import "../../components/pull-request-card/index.js";
import { Pagination } from "../../components/pagination/index.js";
import "./issues-page.css";

const DEFAULT_ISSUES_PER_PAGE = 20;
const ISSUES_PER_PAGE_OPTIONS = [10, 20, 50, 100];

const KNOWN_ISSUE_TYPES = [
  { value: "unrecognized_role", label: "Unrecognized role" },
  { value: "pipeline_error", label: "Pipeline error" },
  { value: "no_info", label: "No info" },
  { value: "no_mayor", label: "No mayor" },
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

  // Issues section
  const [issues, setIssues] = useState([]);
  const [issuesTotal, setIssuesTotal] = useState(0);
  const [issuesPage, setIssuesPage] = useState(getIssuesPageFromUrl());
  const [issuesPerPage, setIssuesPerPage] = useState(getIssuesPerPageFromUrl());
  const [issuesTagFilter, setIssuesTagFilter] = useState(getIssuesTagsFromUrl());
  const [issuesSortDesc, setIssuesSortDesc] = useState(getIssuesSortDescFromUrl());
  const [issuesLoading, setIssuesLoading] = useState(false);
  const [issuesPageLoading, setIssuesPageLoading] = useState(false);

  // Resolve modal state
  const [resolveModal, setResolveModal] = useState(null);
  const [modalScope, setModalScope] = useState("state");
  const [modalState, setModalState] = useState("");
  const [modalLocality, setModalLocality] = useState("");
  const [modalDetails, setModalDetails] = useState(null); // null=not fetched, []=loading, [...]= loaded
  const [prToast, setPrToast] = useState(null);

  // Duplicates section
  const [duplicateJurisdictions, setDuplicateJurisdictions] = useState([]);
  const [duplicateJurisdictionPRs, setDuplicateJurisdictionPRs] = useState({});
  const [openJurisdictions, setOpenJurisdictions] = useState({});
  const [closingStale, setClosingStale] = useState(false);
  const [prState, setPrState] = useState({});

  const [openSections, setOpenSections] = useLocalStorage(
    "issues-page:open-sections",
    { issues: true, duplicates: true },
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

  // Issues — lazy, refetch on any filter/page/sort change
  useEffect(() => {
    if (!openSections.issues) return;
    setIssuesLoading(true);
    fetchJobIssues(issuesTagFilter, issuesPage, issuesPerPage, issuesSortDesc ? "desc" : "asc")
      .then((r) => { setIssues(r.data || []); setIssuesTotal(r.total || 0); })
      .catch(console.error)
      .finally(() => { setIssuesLoading(false); setIssuesPageLoading(false); });
  }, [openSections.issues, issuesPage, issuesPerPage, issuesTagFilter, issuesSortDesc]);

  // Modal details — lazy-fetch when modal opens
  useEffect(() => {
    if (!resolveModal) { setModalDetails(null); return; }
    setModalDetails([]);
    fetchIssueDetails(resolveModal.id)
      .then((r) => setModalDetails(r.data || []))
      .catch(() => setModalDetails([]));
  }, [resolveModal]);

  // Duplicates — lazy, only when section is open
  useEffect(() => {
    if (!openSections.duplicates) return;
    fetchDuplicatePrJurisdictionPipelineRuns()
      .then((r) => setDuplicateJurisdictions(r.data || []))
      .catch(console.error);
  }, [openSections.duplicates]);

  const handleDismissIssue = async (issue) => {
    try {
      await dismissIssue(issue.id);
      setIssues(issues.filter((i) => i.id !== issue.id));
      setIssuesTotal((t) => t - 1);
    } catch (err) {
      console.error("Failed to dismiss issue:", err);
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

  const openResolveModal = (issue) => {
    setResolveModal(issue);
    setModalScope("state");
    setModalState((issue.states || [])[0] || "");
    setModalLocality("");
  };

  const handleModalSubmit = async () => {
    const issue = resolveModal;
    let body = {};
    if (issue.issue_type === "unrecognized_role") {
      body = {
        scope: modalScope,
        ...(modalState ? { state: modalState } : {}),
        ...(modalScope === "locality" && modalLocality ? { locality: modalLocality } : {}),
      };
    }
    try {
      const result = await resolveReviewIssue(issue.id, body);
      setResolveModal(null);
      const pullRequestUrl = result?.data?.pull_request_url;
      if (pullRequestUrl) {
        setIssues(issues.map((i) =>
          i.id === issue.id
            ? { ...i, status: "pr_opened", pull_request_url: pullRequestUrl }
            : i
        ));
        setPrToast({ url: pullRequestUrl, config_path: result?.data?.config_path || null });
        setTimeout(() => setPrToast(null), 8000);
      } else {
        setIssues(issues.filter((i) => i.id !== issue.id));
        setIssuesTotal((t) => t - 1);
      }
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
      const result = await fetchDuplicatePrJurisdictionPipelineRuns();
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

  // --- Source context (lazy-loaded, shared by both modals) ---

  const sourceContextSection = html`
    <div class="issues-page__modal-source">
      <div class="issues-page__modal-source-label">Source context</div>
      ${modalDetails === null || (modalDetails.length === 0 && resolveModal)
        ? html`<div class="issues-page__modal-source-loading">Loading…</div>`
        : modalDetails.map((d) => {
            const urls = [d.url, ...(d.source_urls || [])].filter(Boolean);
            return html`
              <div class="issues-page__modal-source-entry">
                <div class="issues-page__modal-source-header">
                  <span class="issues-page__modal-source-name">${d.jurisdiction_name}</span>
                  ${d.jurisdiction_path ? html`
                    <a class="issues-page__modal-source-link" href="/${d.jurisdiction_path}" target="_blank" rel="noopener noreferrer">view page →</a>
                  ` : null}
                </div>
                ${urls.map((u) => html`<a class="issues-page__modal-source-url" href=${u} target="_blank" rel="noopener noreferrer">${u}</a>`)}
                ${d.people && d.people.length ? html`
                  <div class="issues-page__modal-source-people">${d.people.map((p) => p.name).join(", ")}</div>
                ` : null}
              </div>
            `;
          })
      }
    </div>
  `;

  // --- Modals ---

  const pipelineErrorModal = resolveModal && resolveModal.issue_type === "pipeline_error" ? html`
    <div class="issues-page__modal-overlay" @click=${() => setResolveModal(null)}>
      <div class="issues-page__modal" @click=${(e) => e.stopPropagation()}>
        <h3 class="issues-page__modal-title">Pipeline error</h3>
        ${modalDetails === null || (modalDetails.length === 0 && resolveModal)
          ? html`<div class="issues-page__modal-source-loading">Loading…</div>`
          : html`
            ${modalDetails[0]?.error ? html`<p class="issues-page__modal-meta"><code>${modalDetails[0].error}</code></p>` : null}
            <div class="issues-page__modal-debug-links">
              ${modalDetails[0]?.workflow_log_url ? html`<a href=${modalDetails[0].workflow_log_url} target="_blank" rel="noopener noreferrer">Workflow log →</a>` : null}
              ${modalDetails[0]?.workflow_context_url ? html`<a href=${modalDetails[0].workflow_context_url} target="_blank" rel="noopener noreferrer">Workflow context →</a>` : null}
              ${modalDetails[0]?.debug_url ? html`<a href=${modalDetails[0].debug_url} target="_blank" rel="noopener noreferrer">Cloudflare R2 →</a>` : null}
            </div>
          `}
        <div class="issues-page__modal-actions">
          <button class="btn btn-sm" @click=${() => setResolveModal(null)}>Close</button>
        </div>
      </div>
    </div>
  ` : null;

  const debugLinksModal = resolveModal && ["no_info", "no_mayor"].includes(resolveModal.issue_type) ? html`
    <div class="issues-page__modal-overlay" @click=${() => setResolveModal(null)}>
      <div class="issues-page__modal" @click=${(e) => e.stopPropagation()}>
        <h3 class="issues-page__modal-title">${formatIssueType(resolveModal.issue_type)}</h3>
        ${modalDetails === null || (modalDetails.length === 0 && resolveModal)
          ? html`<div class="issues-page__modal-source-loading">Loading…</div>`
          : html`
            <div class="issues-page__modal-debug-links">
              ${modalDetails[0]?.workflow_log_url ? html`<a href=${modalDetails[0].workflow_log_url} target="_blank" rel="noopener noreferrer">Workflow log →</a>` : null}
              ${modalDetails[0]?.workflow_context_url ? html`<a href=${modalDetails[0].workflow_context_url} target="_blank" rel="noopener noreferrer">Workflow context →</a>` : null}
              ${modalDetails[0]?.debug_url ? html`<a href=${modalDetails[0].debug_url} target="_blank" rel="noopener noreferrer">Cloudflare R2 →</a>` : null}
            </div>
          `}
        <div class="issues-page__modal-actions">
          <button class="btn btn-sm" @click=${() => setResolveModal(null)}>Close</button>
        </div>
      </div>
    </div>
  ` : null;

  const localitiesForState = resolveModal
    ? (resolveModal.jurisdictions || []).filter((j) => j.state === modalState)
    : [];

  const roleModal = resolveModal && resolveModal.issue_type === "unrecognized_role" ? html`
    <div class="issues-page__modal-overlay" @click=${() => setResolveModal(null)}>
      <div class="issues-page__modal" @click=${(e) => e.stopPropagation()}>
        <h3 class="issues-page__modal-title">Resolve: "${resolveModal.issue_key}"</h3>
        ${(resolveModal.states || []).length ? html`
          <p class="issues-page__modal-meta">
            Seen in:
            ${resolveModal.states.map((s) => html`<span class="issues-page__state-badge">${s.toUpperCase()}</span> `)}
          </p>
        ` : null}
        <label>
          Scope
          <select @change=${(e) => { setModalScope(e.target.value); setModalState((resolveModal.states || [])[0] || ""); setModalLocality(""); }}>
            <option value="global" ?selected=${modalScope === "global"}>Global — data_source/local/config.yml</option>
            <option value="state" ?selected=${modalScope === "state"}>State</option>
            <option value="locality" ?selected=${modalScope === "locality"}>Locality</option>
          </select>
        </label>
        ${modalScope === "state" || modalScope === "locality" ? html`
          <label>
            State
            <select @change=${(e) => { setModalState(e.target.value); setModalLocality(""); }}>
              ${(resolveModal.states || []).map((s) => html`
                <option value=${s} ?selected=${s === modalState}>${s.toUpperCase()}</option>
              `)}
            </select>
          </label>
        ` : null}
        ${modalScope === "locality" ? html`
          <label>
            Locality
            <select @change=${(e) => setModalLocality(e.target.value)}>
              <option value="">— select —</option>
              ${localitiesForState.map((j) => html`
                <option value=${j.locality} ?selected=${j.locality === modalLocality}>${j.locality || j.folder}</option>
              `)}
            </select>
          </label>
        ` : null}
        ${sourceContextSection}
        <div class="issues-page__modal-actions">
          <button class="btn btn-sm" @click=${() => setResolveModal(null)}>Cancel</button>
          <button class="btn btn-sm" @click=${handleModalSubmit}>Open PR →</button>
        </div>
      </div>
    </div>
  ` : null;

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
                <th>Status</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${issues.length === 0
                ? html`<tr><td colspan="6">No issues found.</td></tr>`
                : issues.map((ev) => html`
                  <tr>
                    <td><span class="issues-page__issue-type-chip issues-page__issue-type-chip--${ev.issue_type.replace(/_/g, "-")}">${formatIssueType(ev.issue_type)}</span></td>
                    <td class="issues-page__issue-detail">${getIssueDetail(ev.issue_type, ev.issue_key, ev.data)}</td>
                    <td class="issues-page__issue-jurisdictions">
                      ${ev.jurisdictions && ev.jurisdictions.length === 1
                        ? html`
                          <span class="issues-page__state-badge">${ev.jurisdictions[0].state.toUpperCase()}</span>
                          <a href="/${ev.jurisdictions[0].path}" target="_blank" rel="noopener noreferrer">${ev.jurisdictions[0].name}</a>
                        `
                        : (ev.states || []).map((s) => html`<span class="issues-page__state-badge">${s.toUpperCase()}</span>`)
                      }
                    </td>
                    <td class="issues-page__issue-status">
                      ${ev.status === "pr_opened"
                        ? html`<a class="issues-page__issue-status-link" href=${ev.pull_request_url} target="_blank" rel="noopener noreferrer">PR opened →</a>`
                        : html`<span class="issues-page__issue-status-badge">Pending</span>`}
                    </td>
                    <td class="issues-page__issue-date">${formatDate(ev.created_at)}</td>
                    <td class="issues-page__issue-actions">
                      ${ev.status === "pending" && ev.issue_type === "unrecognized_role"
                        ? html`<button class="btn btn-sm" @click=${() => openResolveModal(ev)}>Resolve</button>`
                        : ""}
                      ${["pipeline_error", "no_info", "no_mayor"].includes(ev.issue_type)
                        ? html`<button class="btn btn-sm" @click=${() => openResolveModal(ev)}>Details</button>`
                        : ""}
                      ${ev.status === "pending"
                        ? html`<button class="btn btn-sm" @click=${() => handleDismissIssue(ev)}>Dismiss</button>`
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
      ${issuesSection}
      ${duplicatesSection}
    </main>
    ${pipelineErrorModal}
    ${debugLinksModal}
    ${roleModal}
    ${prToast ? html`
      <div class="issues-page__pr-toast">
        ${prToast.config_path ? html`<code>${prToast.config_path}</code><br>` : null}
        <a href=${prToast.url} target="_blank" rel="noopener noreferrer">View PR →</a>
      </div>
    ` : null}
  `;
}

customElements.define(
  "issues-page",
  component(IssuesPage, { useShadowDOM: false }),
);
export default IssuesPage;
