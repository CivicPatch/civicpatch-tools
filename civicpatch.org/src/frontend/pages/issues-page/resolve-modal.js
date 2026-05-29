import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { KNOWN_ISSUE_TYPES, ISSUE_TYPE } from "../../utils/issue-types.js";
import { fetchIssueDetails, resolveReviewIssue } from "../../api.js";
import { formatIssueType } from "./utils.js";
import "../../components/basic/modal.js";
import "../../components/civ-tab-bar/civ-tab-bar.js";

const SOURCE_CONTEXT_LIMIT = 5;

function getModalTitle(issue, detailsOnly) {
  if (detailsOnly) return formatIssueType(issue.issue_type);
  if (issue.issue_type === ISSUE_TYPE.UNRECOGNIZED_ROLE) return `Resolve: "${issue.issue_key}"`;
  if (issue.issue_type === ISSUE_TYPE.PIPELINE_ERROR) return "Pipeline error";
  return formatIssueType(issue.issue_type);
}

function ResolveModal(host) {
  const issue = host.issue;
  const detailsOnly = host.hasAttribute("details-only");
  const [modalState, setModalState] = useState((issue?.states || [])[0] || "");
  const [modalLocality, setModalLocality] = useState("");
  const [modalDetails, setModalDetails] = useState(null);
  const [showAllDetails, setShowAllDetails] = useState(false);
  const [debugTab, setDebugTab] = useState(0);
  const [logContent, setLogContent] = useState(null);
  const [contextContent, setContextContent] = useState(null);

  useEffect(() => {
    if (!issue) return;
    setModalDetails([]);
    fetchIssueDetails(issue.id)
      .then((r) => setModalDetails(r.data || []))
      .catch(() => setModalDetails([]));
  }, []);

  // Auto-fill locality when the current state has exactly one jurisdiction —
  // the most common case for unrecognized_role issues flagged in a single
  // place. Multi-locality states still require an explicit pick.
  useEffect(() => {
    const matches = (issue?.jurisdictions || []).filter((j) => j.state === modalState);
    if (matches.length === 1) {
      setModalLocality(matches[0].locality);
    } else {
      setModalLocality("");
    }
  }, [modalState, issue?.jurisdictions]);

  const detail = modalDetails?.[0] ?? null;

  useEffect(() => {
    setDebugTab(0);
    setLogContent(null);
    setContextContent(null);
  }, [detail?.request_id]);

  useEffect(() => {
    if (!detail) return;
    const tabKeys = [
      detail.pipeline_run_log_url && "log",
      detail.pipeline_run_context_url && "context",
      detail.debug_url && "cache",
    ].filter(Boolean);
    const tabKey = tabKeys[debugTab];
    if (tabKey === "log" && logContent === null) {
      setLogContent(undefined);
      fetch(detail.pipeline_run_log_url)
        .then((r) => r.text())
        .then((t) => setLogContent(t))
        .catch(() => setLogContent("Failed to load log."));
    }
    if (tabKey === "context" && contextContent === null) {
      setContextContent(undefined);
      fetch(detail.pipeline_run_context_url)
        .then((r) => r.json())
        .then((j) => setContextContent(JSON.stringify(j, null, 2)))
        .catch(() => setContextContent("Failed to load context."));
    }
  }, [debugTab, detail?.request_id]);

  const dispatch = (name, detail) =>
    host.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));

  const handleClose = () => dispatch("modal-close", {});

  const handleSubmit = async () => {
    const body = issue.issue_type === ISSUE_TYPE.UNRECOGNIZED_ROLE
      ? {
          scope: "locality",
          ...(modalState ? { state: modalState } : {}),
          ...(modalLocality ? { locality: modalLocality } : {}),
        }
      : {};
    try {
      const result = await resolveReviewIssue(issue.id, body);
      dispatch("issue-resolved", {
        issue_id: issue.id,
        pull_request_url: result?.data?.pull_request_url || null,
        config_path: result?.data?.config_path || null,
      });
    } catch (err) {
      console.error("Failed to resolve issue:", err);
    }
  };

  if (!issue) return null;

  const issueConfig = KNOWN_ISSUE_TYPES.find((t) => t.value === issue.issue_type);
  if (!issueConfig && !detailsOnly) return null;

  const data = issue.data || {};
  const newUrl = data.discovered_url || data.resolved_url;

  // Type-specific content — one branch per issue type that has unique UI
  const typeExtras =
    issue.issue_type === ISSUE_TYPE.PIPELINE_ERROR
      ? (detail?.error ? html`<p class="issues-page__modal-meta"><code>${detail.error}</code></p>` : null)
    : issue.issue_type === ISSUE_TYPE.DOMAIN_NAVIGATION_ERROR
      ? (data.failure_reason || data.failure_source ? html`
          <div class="issues-page__modal-meta">
            ${data.failure_reason ? html`<p><code>${data.failure_reason}</code></p>` : null}
            ${data.failure_source ? html`<p><code>${data.failure_source}</code></p>` : null}
          </div>
        ` : null)
    : issue.issue_type === ISSUE_TYPE.UNRECOGNIZED_ROLE
      ? html`
        <div class="issues-page__resolve-role-form">
          ${(issue.states || []).length ? html`
            <p class="issues-page__modal-meta">
              Seen in:
              ${issue.states.map((s) => html`<span class="issues-page__state-badge">${s.toUpperCase()}</span> `)}
            </p>
          ` : null}
          <label>
            State
            <select @change=${(e) => setModalState(e.target.value)}>
              ${(issue.states || []).map((s) => html`
                <option value=${s} ?selected=${s === modalState}>${s.toUpperCase()}</option>
              `)}
            </select>
          </label>
          <label>
            Locality
            <select @change=${(e) => setModalLocality(e.target.value)}>
              <option value="">— select —</option>
              ${(issue.jurisdictions || []).filter((j) => j.state === modalState).map((j) => html`
                <option value=${j.locality} ?selected=${j.locality === modalLocality}>${j.locality || j.folder}</option>
              `)}
            </select>
          </label>
        </div>
      `
    : null;

  // Domain change info — shown when the issue data carries a URL change
  const domainChangeExtras = data.original_url ? html`
    <p class="issues-page__modal-meta">
      Configured URL: <a href=${data.original_url} target="_blank" rel="noopener noreferrer">${data.original_url}</a>
    </p>
    ${newUrl ? html`
      <p class="issues-page__modal-meta">
        New URL: <a href=${newUrl} target="_blank" rel="noopener noreferrer">${newUrl}</a>
      </p>
    ` : null}
  ` : null;

  const debugTabs = detail ? [
    detail.pipeline_run_log_url && { label: "Logs" },
    detail.pipeline_run_context_url && { label: "Context" },
    detail.debug_url && { label: "Cache" },
  ].filter(Boolean) : [];

  const activeTabKeys = detail ? [
    detail.pipeline_run_log_url && "log",
    detail.pipeline_run_context_url && "context",
    detail.debug_url && "cache",
  ].filter(Boolean) : [];

  const activeTabKey = activeTabKeys[Math.min(debugTab, activeTabKeys.length - 1)];

  const debugSection = !detail || debugTabs.length === 0 ? null : html`
    <div class="issues-page__modal-debug">
      <civ-tab-bar
        .tabs=${debugTabs}
        .selectedIndex=${Math.min(debugTab, debugTabs.length - 1)}
        .onTabClick=${(idx) => setDebugTab(idx)}
      ></civ-tab-bar>
      <div class="issues-page__modal-debug-content">
        ${activeTabKey === "log" ? html`
          ${logContent == null
            ? html`<span class="issues-page__modal-source-loading">Loading…</span>`
            : html`<pre class="issues-page__modal-debug-pre">${logContent}</pre>`}
        ` : null}
        ${activeTabKey === "context" ? html`
          ${contextContent == null
            ? html`<span class="issues-page__modal-source-loading">Loading…</span>`
            : html`<pre class="issues-page__modal-debug-pre">${contextContent}</pre>`}
        ` : null}
        ${activeTabKey === "cache" ? html`
          <div class="issues-page__modal-debug-cache">
            <a href=${detail.debug_url} target="_blank" rel="noopener noreferrer">Open in Cloudflare R2 →</a>
          </div>
        ` : null}
      </div>
    </div>
  `;

  const sourceSection = html`
    <div class="issues-page__modal-source">
      <div class="issues-page__modal-source-label">Source context</div>
      ${modalDetails === null || (modalDetails.length === 0 && issue)
        ? html`<div class="issues-page__modal-source-loading">Loading…</div>`
        : html`
          ${(showAllDetails ? modalDetails : modalDetails.slice(0, SOURCE_CONTEXT_LIMIT)).map((d) => {
            const urls = [...new Set([d.url, ...(d.source_urls || [])].filter(Boolean))];
            return html`
              <div class="issues-page__modal-source-entry">
                <div class="issues-page__modal-source-header">
                  <span class="issues-page__modal-source-name">${d.jurisdiction_name}</span>
                  ${d.jurisdiction_path ? html`
                    <a class="issues-page__modal-source-link" href="/${d.jurisdiction_path}" target="_blank" rel="noopener noreferrer">view page →</a>
                  ` : null}
                </div>
                ${urls.map((u) => html`<a class="issues-page__modal-source-url" href=${u} target="_blank" rel="noopener noreferrer">${u}</a>`)}
                ${d.people?.length ? html`
                  <div class="issues-page__modal-source-people">${d.people.map((p) => p.name).join(", ")}</div>
                ` : null}
              </div>
            `;
          })}
          ${modalDetails.length > SOURCE_CONTEXT_LIMIT ? html`
            <button class="btn-ghost issues-page__modal-source-toggle" @click=${() => setShowAllDetails(!showAllDetails)}>
              ${showAllDetails ? "Show less" : `Show all ${modalDetails.length}`}
            </button>
          ` : null}
        `
      }
    </div>
  `;

  const isResolvable = issue.issue_type === ISSUE_TYPE.UNRECOGNIZED_ROLE;

  const content = html`
    <div class="issues-page__resolve-content">
      ${typeExtras}
      ${domainChangeExtras}
      ${debugSection}
      ${sourceSection}
    </div>
  `;

  const footer = isResolvable
    ? html`
      <button class="btn btn-sm secondary" @click=${handleClose}>Cancel</button>
      <button class="btn btn-sm" @click=${handleSubmit}>Open PR →</button>
    `
    : html`<button class="btn btn-sm secondary" @click=${handleClose}>Close</button>`;

  return html`
    <civ-modal
      .title=${getModalTitle(issue, detailsOnly)}
      .content=${content}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleClose }}
    ></civ-modal>
  `;
}

customElements.define("issues-resolve-modal", component(ResolveModal, { useShadowDOM: false, observedAttributes: ["details-only"] }));
