import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { KNOWN_ISSUE_TYPES, ISSUE_TYPE } from "../../utils/issue-types.js";
import { fetchIssueDetails, resolveReviewIssue } from "../../api.js";
import { formatIssueType } from "./utils.js";
import "../../components/basic/modal.js";
import "../../components/civ-tab-bar/civ-tab-bar.js";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";

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

  const detail = modalDetails?.[0] ?? null;

  useEffect(() => {
    setDebugTab(0);
    setLogContent(null);
    setContextContent(null);
  }, [detail?.changeset_id]);

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
  }, [debugTab, detail?.changeset_id]);

  const dispatch = (name, detail) =>
    host.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));

  const handleClose = () => dispatch("modal-close", {});

  const handleSubmit = async () => {
    try {
      const result = await resolveReviewIssue(issue.id);
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

  // Per-type metadata blocks — the UI unique to each issue type. renderBody() (below)
  // decides which of these, and which shared sections, each issue type composes into its view.
  const pipelineErrorMeta = detail?.error
    ? html`<p class="issues-page__modal-meta"><code>${detail.error}</code></p>`
    : null;

  const mergeFailedMeta = data.error || data.mergeable_state ? html`
    <div class="issues-page__modal-meta">
      ${data.error ? html`<p><code>${data.error}</code></p>` : null}
      ${data.mergeable_state ? html`<p>Mergeable state: <code>${data.mergeable_state}</code></p>` : null}
    </div>
  ` : null;

  const domainNavigationMeta = data.failure_reason || data.failure_source ? html`
    <div class="issues-page__modal-meta">
      ${data.failure_reason ? html`<p><code>${data.failure_reason}</code></p>` : null}
      ${data.failure_source ? html`<p><code>${data.failure_source}</code></p>` : null}
    </div>
  ` : null;

  // The state/locality pickers that used to live here are gone with migration
  // 109: the taxonomy is one flat global list, so resolving has nothing to
  // target. "Seen in" stays — it is context for the decision, not an input.
  const unrecognizedRoleForm = (issue.states || []).length
    ? html`
      <div class="issues-page__resolve-role-form">
        <p class="issues-page__modal-meta">
          Seen in:
          ${issue.states.map((s) => html`<span class="issues-page__state-badge">${s.toUpperCase()}</span> `)}
        </p>
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
                    <a class="issues-page__modal-source-link" href="/${jurisdictionOcdidToPath(d.jurisdiction_path)}" target="_blank" rel="noopener noreferrer">view page →</a>
                  ` : null}
                </div>
                ${urls.map((u) => html`<a class="issues-page__modal-source-url" href=${u} target="_blank" rel="noopener noreferrer">${u}</a>`)}
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

  // Sections common to pipeline/domain issues: a URL change, pipeline debug tabs, and the
  // scraped source context. merge_failed deliberately skips the first two — a merge failure
  // is about the PR's state and the failing jurisdiction, not pipeline run artifacts.
  const sharedSections = html`${domainChangeExtras}${debugSection}${sourceSection}`;

  function renderBody() {
    switch (issue.issue_type) {
      case ISSUE_TYPE.MERGE_FAILED:
        return html`${mergeFailedMeta}${sourceSection}`;
      case ISSUE_TYPE.PIPELINE_ERROR:
        return html`${pipelineErrorMeta}${sharedSections}`;
      case ISSUE_TYPE.DOMAIN_NAVIGATION_ERROR:
        return html`${domainNavigationMeta}${sharedSections}`;
      case ISSUE_TYPE.UNRECOGNIZED_ROLE:
        return html`${unrecognizedRoleForm}${sharedSections}`;
      default:
        return sharedSections;
    }
  }

  const content = html`
    <div class="issues-page__resolve-content">
      ${renderBody()}
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
