import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { useAuth } from "../../hooks/useAuth.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import {
  fetchJobIssues,
  fetchIssueDetails,
  resolveReviewIssue,
  dismissIssue,
  fetchNotes,
  createNote,
} from "../../api.js";
import { Pagination } from "../../components/pagination/index.js";
import "../../components/search-jurisdictions/select-state.js";
import { ISSUE_TYPE, KNOWN_ISSUE_TYPES } from "../../utils/issue-types.js";
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


function getIssueTypeConfig(issueType) {
  return KNOWN_ISSUE_TYPES.find((t) => t.value === issueType);
}

function getIssueDetail(issueType, issueKey, data) {
  if (!data) return issueKey || "";
  if (issueType === ISSUE_TYPE.UNRECOGNIZED_ROLE) {
    const names = (data.person_names || []).join(", ");
    return names ? `${issueKey} — ${names}` : issueKey;
  }
  return issueKey;
}

function formatIssueType(issueType) {
  return getIssueTypeConfig(issueType)?.label ?? issueType;
}

function formatDate(isoString) {
  if (!isoString) return "";
  return new Date(isoString).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function IssuesPage() {
  const { permissions } = useAuth();

  const [defaultState, setDefaultState] = useLocalStorage("app:default-state", "", { ttl: PERSIST_FOREVER });
  const [stateCode, setStateCode] = useState(getStateFromUrl() || defaultState);

  // Issues section
  const [issues, setIssues] = useState([]);
  const [issuesTotal, setIssuesTotal] = useState(0);
  const [issuesPage, setIssuesPage] = useState(getIssuesPageFromUrl());
  const [issuesPerPage, setIssuesPerPage] = useState(getIssuesPerPageFromUrl());
  const [issuesTagFilter, setIssuesTagFilter] = useState(getIssuesTagsFromUrl());
  const [issuesSortDesc, setIssuesSortDesc] = useState(getIssuesSortDescFromUrl());
  const [issuesLoading, setIssuesLoading] = useState(false);
  const [issuesPageLoading, setIssuesPageLoading] = useState(false);
  const [showArchived, setShowArchived] = useState(false);

  // Resolve modal state
  const [resolveModal, setResolveModal] = useState(null);
  const [resolveModalDetailsOnly, setResolveModalDetailsOnly] = useState(false);
  const [modalScope, setModalScope] = useState("state");
  const [modalState, setModalState] = useState("");
  const [modalLocality, setModalLocality] = useState("");
  const [modalDetails, setModalDetails] = useState(null); // null=not fetched, []=loading, [...]= loaded
  const [prToast, setPrToast] = useState(null);
  const [showAllModalDetails, setShowAllModalDetails] = useState(false);

  // Dismiss modal state
  const [dismissModal, setDismissModal] = useState(null); // issue being dismissed
  const [dismissNote, setDismissNote] = useState("");
  const [dismissNotes, setDismissNotes] = useState(null); // existing notes for jurisdiction
  const [dismissLoading, setDismissLoading] = useState(false);

  const [openSections, setOpenSections] = useLocalStorage(
    "issues-page:open-sections",
    { issues: true },
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
      setStateCode(getStateFromUrl());
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  // Issues — lazy, refetch on any filter/page/sort change
  useEffect(() => {
    if (!openSections.issues) return;
    setIssuesLoading(true);
    fetchJobIssues(issuesTagFilter, issuesPage, issuesPerPage, issuesSortDesc ? "desc" : "asc", stateCode, showArchived)
      .then((r) => { setIssues(r.data || []); setIssuesTotal(r.total || 0); })
      .catch(console.error)
      .finally(() => { setIssuesLoading(false); setIssuesPageLoading(false); });
  }, [openSections.issues, issuesPage, issuesPerPage, issuesTagFilter, issuesSortDesc, stateCode, showArchived]);

  // Modal details — lazy-fetch when modal opens
  useEffect(() => {
    if (!resolveModal) { setModalDetails(null); return; }
    setModalDetails([]);
    fetchIssueDetails(resolveModal.id)
      .then((r) => setModalDetails(r.data || []))
      .catch(() => setModalDetails([]));
  }, [resolveModal]);

  const openDismissModal = (issue) => {
    setDismissModal(issue);
    setDismissNote("");
    setDismissNotes(null);
    const ocdid = issue.jurisdictions?.[0]?.jurisdiction_ocdid;
    if (ocdid) {
      fetchNotes(ocdid, 1, 5)
        .then((r) => setDismissNotes(r.data || []))
        .catch(() => setDismissNotes([]));
    } else {
      setDismissNotes([]);
    }
  };

  const closeDismissModal = () => { setDismissModal(null); setDismissNote(""); setDismissNotes(null); };

  const handleConfirmDismiss = async () => {
    if (!dismissModal) return;
    setDismissLoading(true);
    try {
      const ocdid = dismissModal.jurisdictions?.[0]?.jurisdiction_ocdid;
      const label = formatIssueType(dismissModal.issue_type);
      const noteBody = dismissNote.trim()
        ? `Dismissed — ${label}: ${dismissNote.trim()}`
        : `Dismissed — ${label}`;
      if (ocdid) await createNote(ocdid, noteBody);
      await dismissIssue(dismissModal.id);
      setIssues(issues.filter((i) => i.id !== dismissModal.id));
      setIssuesTotal((t) => t - 1);
      closeDismissModal();
    } catch (err) {
      console.error("Failed to dismiss issue:", err);
    } finally {
      setDismissLoading(false);
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

  const openDetailsModal = (issue) => {
    setResolveModal(issue);
    setResolveModalDetailsOnly(true);
  };

  const openResolveModal = (issue) => {
    setResolveModal(issue);
    setResolveModalDetailsOnly(false);
    setModalScope("state");
    setModalState((issue.states || [])[0] || "");
    setModalLocality("");
  };

  const handleModalSubmit = async () => {
    const issue = resolveModal;
    let body = {};
    if (issue.issue_type === ISSUE_TYPE.UNRECOGNIZED_ROLE) {
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

  const issuesTotalPages = Math.ceil(issuesTotal / issuesPerPage);

  // --- Source context (lazy-loaded, shared by both modals) ---

  const SOURCE_CONTEXT_LIMIT = 5;
  const sourceContextSection = html`
    <div class="issues-page__modal-source">
      <div class="issues-page__modal-source-label">Source context</div>
      ${modalDetails === null || (modalDetails.length === 0 && resolveModal)
        ? html`<div class="issues-page__modal-source-loading">Loading…</div>`
        : html`
          ${(showAllModalDetails ? modalDetails : modalDetails.slice(0, SOURCE_CONTEXT_LIMIT)).map((d) => {
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
            })}
          ${modalDetails.length > SOURCE_CONTEXT_LIMIT ? html`
            <button class="btn-ghost issues-page__modal-source-toggle" @click=${() => setShowAllModalDetails(!showAllModalDetails)}>
              ${showAllModalDetails ? "Show less" : `Show all ${modalDetails.length}`}
            </button>
          ` : null}
        `
      }
    </div>
  `;

  // --- Modals ---

  const debugLinks = !modalDetails
    ? html`<div class="issues-page__modal-debug-links"><span class="issues-page__modal-source-loading">Loading…</span></div>`
    : modalDetails.length === 1
    ? html`
      <div class="issues-page__modal-debug-links">
        ${modalDetails[0]?.workflow_log_url ? html`<a href=${modalDetails[0].workflow_log_url} target="_blank" rel="noopener noreferrer">Workflow log →</a>` : null}
        ${modalDetails[0]?.workflow_context_url ? html`<a href=${modalDetails[0].workflow_context_url} target="_blank" rel="noopener noreferrer">Workflow context →</a>` : null}
        ${modalDetails[0]?.debug_url ? html`<a href=${modalDetails[0].debug_url} target="_blank" rel="noopener noreferrer">Cloudflare R2 →</a>` : null}
      </div>
    `
    : null;

  const modalLoading = html`<div class="issues-page__modal-source-loading">Loading…</div>`;

  const closeModal = () => { setResolveModal(null); setResolveModalDetailsOnly(false); setShowAllModalDetails(false); };

  function renderModalContent() {
    if (!resolveModal) return null;
    const modalType = resolveModalDetailsOnly ? "details" : getIssueTypeConfig(resolveModal.issue_type)?.modal_type;
    switch (modalType) {
      case "pipeline_error":
        return html`
          <h3 class="issues-page__modal-title">Pipeline error</h3>
          ${modalDetails?.[0]?.error ? html`<p class="issues-page__modal-meta"><code>${modalDetails[0].error}</code></p>` : null}
          ${debugLinks}
          <div class="issues-page__modal-actions">
            <button class="btn btn-sm secondary" @click=${closeModal}>Close</button>
          </div>
        `;
      case "debug":
      case "details": {
        const d0 = modalDetails?.[0];
        return html`
          <div class="issues-page__modal-header">
            <h3 class="issues-page__modal-title">${formatIssueType(resolveModal.issue_type)}</h3>
            ${d0?.jurisdiction_path ? html`<a class="issues-page__modal-jurisdiction-link" href="/${d0.jurisdiction_path}" target="_blank" rel="noopener noreferrer">${d0.jurisdiction_name || d0.jurisdiction_path}</a>` : null}
            ${d0?.url ? html`<a class="issues-page__modal-source-url" href=${d0.url} target="_blank" rel="noopener noreferrer">${d0.url}</a>` : null}
          </div>
          ${debugLinks}
          ${sourceContextSection}
          <div class="issues-page__modal-actions">
            <button class="btn btn-sm secondary" @click=${closeModal}>Close</button>
          </div>
        `;
      }
      default:
        return null;
    }
  }

  const debugModal = resolveModal && (resolveModalDetailsOnly || getIssueTypeConfig(resolveModal.issue_type)?.modal_type !== "role") ? html`
    <div class="issues-page__modal-overlay" @click=${closeModal}>
      <div class="issues-page__modal" @click=${(e) => e.stopPropagation()}>
        ${renderModalContent()}
      </div>
    </div>
  ` : null;

  const localitiesForState = resolveModal
    ? (resolveModal.jurisdictions || []).filter((j) => j.state === modalState)
    : [];

  const roleModal = resolveModal && !resolveModalDetailsOnly && resolveModal.issue_type === ISSUE_TYPE.UNRECOGNIZED_ROLE ? html`
    <div class="issues-page__modal-overlay" @click=${closeModal}>
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
          <button class="btn btn-sm secondary" @click=${closeModal}>Cancel</button>
          <button class="btn btn-sm" @click=${handleModalSubmit}>Open PR →</button>
        </div>
      </div>
    </div>
  ` : null;

  // --- Render helpers ---

  function renderIssueRow(ev) {
    const config = getIssueTypeConfig(ev.issue_type);
    const categoryClass = config?.category ? ` issues-page__issue-type-chip--${config.category}` : "";
    return html`
      <tr>
        <td><span class="issues-page__issue-type-chip issues-page__issue-type-chip--${ev.issue_type.replace(/_/g, "-")}${categoryClass}">${formatIssueType(ev.issue_type)}</span></td>
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
          <button class="btn btn-sm secondary" @click=${() => openDetailsModal(ev)}>Details</button>
          ${config?.modal_type === "role" && ev.status === "pending"
            ? html`<button class="btn btn-sm" @click=${() => openResolveModal(ev)}>Resolve</button>`
            : ""}
          ${ev.status === "pending"
            ? html`<button class="btn btn-sm destructive" @click=${() => openDismissModal(ev)}>Dismiss</button>`
            : ""}
        </td>
      </tr>
    `;
  }

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
      >${label}${active ? html` <span class="issues-page__issue-tag-x">×</span>` : ""}</button>
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
          <div class="issues-page__issue-tags">${!showArchived ? tagChips : null}</div>
          <button
            class="btn btn-sm issues-page__sort-btn"
            @click=${handleToggleSort}
          >${issuesSortDesc ? "Newest ↓" : "Oldest ↑"}</button>
          <button
            class="btn btn-sm"
            @click=${() => { setShowArchived(!showArchived); setIssuesPage(1); }}
          >${showArchived ? "← Active Issues" : "Archived"}</button>
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
                  ${renderIssueRow(ev)}
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

  return html`
    <main class="issues-page page-content">
      <div class="issues-page__filters">
        <civ-select-state
          .selected=${stateCode}
          @state-change=${handleStateChange}
        ></civ-select-state>
      </div>
      ${issuesSection}
    </main>
    ${debugModal}
    ${roleModal}
    ${dismissModal ? html`
      <div class="issues-page__modal-overlay" @click=${closeDismissModal}>
        <div class="issues-page__modal" @click=${(e) => e.stopPropagation()}>
          <h3 class="issues-page__modal-title">Dismiss — ${formatIssueType(dismissModal.issue_type)}</h3>
          ${dismissModal.jurisdictions?.length === 1 ? html`
            <div class="issues-page__modal-jurisdiction-link">${dismissModal.jurisdictions[0].name}</div>
          ` : null}
          ${dismissNotes === null ? html`<div class="issues-page__modal-source-loading">Loading notes…</div>` : dismissNotes.length ? html`
            <div class="issues-page__modal-source">
              <div class="issues-page__modal-source-label">Recent notes</div>
              ${dismissNotes.map((n) => html`
                <div class="issues-page__modal-source-entry">
                  <div class="issues-page__modal-source-people">${n.created_by_display_name || "Unknown"} · ${formatDate(n.created_at)}</div>
                  <div>${n.body}</div>
                </div>
              `)}
            </div>
          ` : null}
          <label>
            Note <span class="issues-page__modal-optional">(optional)</span>
            <textarea
              class="issues-page__dismiss-note"
              placeholder="Reason for dismissing…"
              rows="3"
              .value=${dismissNote}
              @input=${(e) => setDismissNote(e.target.value)}
            ></textarea>
          </label>
          <div class="issues-page__modal-actions">
            <button class="btn btn-sm secondary" @click=${closeDismissModal} ?disabled=${dismissLoading}>Cancel</button>
            <button class="btn btn-sm" @click=${handleConfirmDismiss} ?disabled=${dismissLoading}>
              ${dismissLoading ? "Dismissing…" : "Confirm"}
            </button>
          </div>
        </div>
      </div>
    ` : null}
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
