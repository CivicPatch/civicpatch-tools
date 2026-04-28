import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { fetchJobIssues, fetchIssueCounts, flagIssue } from "../../api.js";
import { Pagination } from "../../components/pagination/index.js";
import "../../components/search-jurisdictions/select-state.js";
import { KNOWN_ISSUE_TYPES } from "../../utils/issue-types.js";
import { IssueRow } from "./issue-row.js";
import "./config-editor.js";
import "./dismiss-modal.js";
import "./resolve-modal.js";
import "./issues-page.css";

const DEFAULT_ISSUES_PER_PAGE = 20;
const ISSUES_PER_PAGE_OPTIONS = [10, 20, 50, 100];

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

function getStateFromUrl() {
  const val = new URLSearchParams(window.location.search).get("state");
  return val ? val.toLowerCase() : "";
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

function IssuesPage() {
  const { permissions } = useAuth();

  const [defaultState, setDefaultState] = useLocalStorage("app:default-state", "", { ttl: PERSIST_FOREVER });
  const [stateCode, setStateCode] = useState(getStateFromUrl() || defaultState);

  const [issues, setIssues] = useState([]);
  const [issuesTotal, setIssuesTotal] = useState(0);
  const [issuesPage, setIssuesPage] = useState(getIssuesPageFromUrl());
  const [issuesPerPage, setIssuesPerPage] = useState(getIssuesPerPageFromUrl());
  const [issuesTagFilter, setIssuesTagFilter] = useState(getIssuesTagsFromUrl());
  const [issuesSortDesc, setIssuesSortDesc] = useState(getIssuesSortDescFromUrl());
  const [issuesLoading, setIssuesLoading] = useState(false);
  const [issuesPageLoading, setIssuesPageLoading] = useState(false);
  const [showArchived, setShowArchived] = useState(false);

  const [issueCounts, setIssueCounts] = useState({});

  const [resolveModal, setResolveModal] = useState(null);
  const [dismissModal, setDismissModal] = useState(null);
  const [configModal, setConfigModal] = useState(null);
  const [prToast, setPrToast] = useState(null);

  const [openSections, setOpenSections] = useLocalStorage(
    "issues-page:open-sections",
    { issues: true, roleConfigs: false },
    { ttl: PERSIST_FOREVER },
  );
  const toggleSection = (key) => setOpenSections({ ...openSections, [key]: !openSections[key] });

  useEffect(() => {
    const onPopState = () => {
      setIssuesPage(getIssuesPageFromUrl());
      setIssuesPerPage(getIssuesPerPageFromUrl());
      setIssuesTagFilter(getIssuesTagsFromUrl());
      setIssuesSortDesc(getIssuesSortDescFromUrl());
      setStateCode(getStateFromUrl());
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    fetchIssueCounts(stateCode).then((r) => setIssueCounts(r.data || {})).catch(() => {});
  }, [stateCode]);

  useEffect(() => {
    if (!openSections.issues) return;
    setIssuesLoading(true);
    fetchJobIssues(issuesTagFilter, issuesPage, issuesPerPage, issuesSortDesc ? "desc" : "asc", stateCode, showArchived)
      .then((r) => { setIssues(r.data || []); setIssuesTotal(r.total || 0); })
      .catch(console.error)
      .finally(() => { setIssuesLoading(false); setIssuesPageLoading(false); });
  }, [openSections.issues, issuesPage, issuesPerPage, issuesTagFilter, issuesSortDesc, stateCode, showArchived]);

  const openDetailsModal = (issue) => setResolveModal(issue);
  const closeModal = () => setResolveModal(null);
  const closeDismissModal = () => setDismissModal(null);

  const handleIssueResolved = (e) => {
    const { issue_id, pull_request_url, config_path } = e.detail;
    setResolveModal(null);
    if (pull_request_url) {
      setIssues(issues.map((i) => i.id === issue_id ? { ...i, status: "pr_opened", pull_request_url } : i));
      setPrToast({ url: pull_request_url, config_path: config_path || null });
      setTimeout(() => setPrToast(null), 8000);
    } else {
      setIssues(issues.filter((i) => i.id !== issue_id));
      setIssuesTotal((t) => t - 1);
    }
  };

  const handleIssueFlag = (issue, is_flagged) => {
    setIssues(issues.map((i) => i.id === issue.id ? { ...i, is_flagged } : i));
    flagIssue(issue.id, is_flagged).catch(() => {
      setIssues(issues.map((i) => i.id === issue.id ? { ...i, is_flagged: !is_flagged } : i));
    });
  };

  const handleIssueDismissed = (e) => {
    setDismissModal(null);
    setIssues(issues.filter((i) => i.id !== e.detail.issue_id));
    setIssuesTotal((t) => t - 1);
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

  const handleStateChange = (e) => {
    const newState = e.detail.state;
    const params = new URLSearchParams(window.location.search);
    if (newState) params.set("state", newState);
    else params.delete("state");
    params.set("issues_page", 1);
    window.history.pushState({}, "", `${window.location.pathname}?${params}`);
    setDefaultState(newState || "");
    setStateCode(newState || "");
    setIssuesPage(1);
  };

  const issuesTotalPages = Math.ceil(issuesTotal / issuesPerPage);

  const issuesPaginationControls = !issuesPageLoading ? Pagination({
    page: issuesPage,
    totalPages: issuesTotalPages,
    onPrevious: () => goToIssuesPage(issuesPage - 1),
    onNext: () => goToIssuesPage(issuesPage + 1),
    onGoToPage: goToIssuesPage,
    hrefForPage: (n) => `?issues_page=${n}`,
  }) : null;

  const tagChips = KNOWN_ISSUE_TYPES.map(({ value, label, category }) => {
    const active = issuesTagFilter.includes(value);
    const categoryClass = category ? ` issues-page__issue-tag--${category}` : "";
    return html`
      <button
        class="issues-page__issue-tag${categoryClass}${active ? " issues-page__issue-tag--active" : ""}"
        @click=${() => handleToggleTag(value)}
      >${label}${issueCounts[value] ? html` <span class="issues-page__issue-tag-count">${issueCounts[value]}</span>` : ""}${active ? html` <span class="issues-page__issue-tag-x">×</span>` : ""}</button>
    `;
  });

  const issuesSection = html`
    <section class="issues-page__section">
      <div class="issues-page__section-header" @click=${() => toggleSection("issues")}>
        <h2 class="issues-page__section-title issues-page__section-title--info">${showArchived ? "Archived Issues" : "Issues"} <span class="issues-page__section-count">${issuesTotal || ""}</span></h2>
        <i class="fa-solid fa-chevron-down btn-icon${openSections.issues ? " btn-icon--rotated" : ""}"></i>
      </div>
      ${openSections.issues ? html`
        <div class="issues-page__issues-filters">
          <div class="issues-page__issue-tags">${tagChips}</div>
          <button class="btn btn-sm issues-page__sort-btn" @click=${handleToggleSort}>${issuesSortDesc ? "Newest ↓" : "Oldest ↑"}</button>
          <button class="btn btn-sm" @click=${() => { setShowArchived(!showArchived); setIssuesPage(1); }}>${showArchived ? "← Active Issues" : "Archived"}</button>
        </div>
        ${issuesLoading ? html`<div>Loading…</div>` : html`
          <table class="issues-page__issues-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Detail</th>
                <th>Jurisdiction</th>
                <th>Status</th>
                <th class="issues-page__issue-flag">Flagged</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${issues.length === 0
                ? html`<tr><td colspan="6">No issues found.</td></tr>`
                : issues.map((ev) => IssueRow(ev, {
                    onDetails: openDetailsModal,
                    onDismiss: (issue) => setDismissModal(issue),
                    onConfig: (jurisdictions) => setConfigModal({ jurisdictions, initialView: "merged" }),
                    onFlag: handleIssueFlag,
                  }))
              }
            </tbody>
          </table>
          <div class="issues-page__top-controls">
            <div class="issues-page__pagination">${issuesPaginationControls}</div>
            <label class="issues-page__per-page">
              Per page
              <select @change=${handleIssuesPerPageChange}>
                ${ISSUES_PER_PAGE_OPTIONS.map((n) => html`<option value=${n} ?selected=${n === issuesPerPage}>${n}</option>`)}
              </select>
            </label>
          </div>
        `}
      ` : null}
    </section>
  `;

  const roleConfigsSection = html`
    <section class="issues-page__section">
      <div class="issues-page__section-header" @click=${() => toggleSection("roleConfigs")}>
        <h2 class="issues-page__section-title issues-page__section-title--warning">Role Configs</h2>
        <i class="fa-solid fa-chevron-down btn-icon${openSections.roleConfigs ? " btn-icon--rotated" : ""}"></i>
      </div>
      ${openSections.roleConfigs ? html`
        <issues-config-editor .inline=${true} .stateCode=${stateCode}></issues-config-editor>
      ` : null}
    </section>
  `;

  return html`
    <main class="issues-page page-content">
      <div class="issues-page__filters">
        <civ-select-state .selected=${stateCode} @state-change=${handleStateChange}></civ-select-state>
      </div>
      ${roleConfigsSection}
      ${issuesSection}
    </main>

    ${resolveModal ? html`
      <issues-resolve-modal
        .issue=${resolveModal}
        ?details-only=${true}
        @modal-close=${closeModal}
        @issue-resolved=${handleIssueResolved}
      ></issues-resolve-modal>
    ` : null}

    ${dismissModal ? html`
      <issues-dismiss-modal
        .issue=${dismissModal}
        @modal-close=${closeDismissModal}
        @issue-dismissed=${handleIssueDismissed}
      ></issues-dismiss-modal>
    ` : null}

    ${configModal ? html`
      <issues-config-editor
        .jurisdictions=${configModal.jurisdictions}
        .initialView=${configModal.initialView}
        @modal-close=${() => setConfigModal(null)}
      ></issues-config-editor>
    ` : null}

    ${prToast ? html`
      <div class="issues-page__pr-toast">
        ${prToast.config_path ? html`<code>${prToast.config_path}</code><br>` : null}
        <a href=${prToast.url} target="_blank" rel="noopener noreferrer">View PR →</a>
      </div>
    ` : null}
  `;
}

customElements.define("issues-page", component(IssuesPage, { useShadowDOM: false }));
export default IssuesPage;
