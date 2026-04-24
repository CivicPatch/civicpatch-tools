import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { KNOWN_ISSUE_TYPES } from "../../utils/issue-types.js";
import { fetchIssueDetails, resolveReviewIssue } from "../../api.js";
import { formatIssueType } from "./utils.js";
import { useAuth } from "../../hooks/useAuth.js";
import "../../components/basic/modal.js";

const SOURCE_CONTEXT_LIMIT = 5;

function getModalTitle(modalType, issue) {
  switch (modalType) {
    case "pipeline_error": return "Pipeline error";
    case "domain_inactive_fixed": return "Resolve: Inactive domain";
    case "role": return `Resolve: "${issue.issue_key}"`;
    default: return formatIssueType(issue.issue_type);
  }
}

function ResolveModal(host) {
  const issue = host.issue;
  const detailsOnly = host.hasAttribute("details-only");
  const { permissions } = useAuth();

  const [modalScope, setModalScope] = useState("state");
  const [modalState, setModalState] = useState((issue?.states || [])[0] || "");
  const [modalLocality, setModalLocality] = useState("");
  const [modalDetails, setModalDetails] = useState(null);
  const [showAllDetails, setShowAllDetails] = useState(false);

  useEffect(() => {
    if (!issue) return;
    setModalDetails([]);
    fetchIssueDetails(issue.id)
      .then((r) => setModalDetails(r.data || []))
      .catch(() => setModalDetails([]));
  }, []);

  const dispatch = (name, detail) =>
    host.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));

  const handleClose = () => dispatch("modal-close", {});

  const handleSubmit = async () => {
    const modalType = KNOWN_ISSUE_TYPES.find((t) => t.value === issue.issue_type)?.modal_type;
    const body = modalType === "role"
      ? {
          scope: modalScope,
          ...(modalState ? { state: modalState } : {}),
          ...(modalScope === "locality" && modalLocality ? { locality: modalLocality } : {}),
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

  const modalType = detailsOnly
    ? "details"
    : KNOWN_ISSUE_TYPES.find((t) => t.value === issue.issue_type)?.modal_type;

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

  let content = null;
  let footer = null;

  switch (modalType) {
    case "pipeline_error":
      content = html`
        ${modalDetails?.[0]?.error ? html`<p class="issues-page__modal-meta"><code>${modalDetails[0].error}</code></p>` : null}
        ${debugLinks}
      `;
      footer = html`<button class="btn btn-sm secondary" @click=${handleClose}>Close</button>`;
      break;
    case "debug":
    case "details": {
      const d0 = modalDetails?.length === 1 ? modalDetails[0] : null;
      const data = issue.data || {};
      const newUrl = data.discovered_url || data.resolved_url;
      content = html`
        ${data.original_url ? html`
          <p class="issues-page__modal-meta">
            From: <a href=${data.original_url} target="_blank" rel="noopener noreferrer">${data.original_url}</a>
          </p>
        ` : null}
        ${newUrl ? html`
          <p class="issues-page__modal-meta">
            To: <a href=${newUrl} target="_blank" rel="noopener noreferrer">${newUrl}</a>
          </p>
        ` : null}
        ${d0?.jurisdiction_path ? html`<a class="issues-page__modal-jurisdiction-link" href="/${d0.jurisdiction_path}" target="_blank" rel="noopener noreferrer">${d0.jurisdiction_name || d0.jurisdiction_path}</a>` : null}
        ${d0?.url ? html`<a class="issues-page__modal-source-url" href=${d0.url} target="_blank" rel="noopener noreferrer">${d0.url}</a>` : null}
        ${debugLinks}
        ${sourceSection}
      `;
      footer = html`<button class="btn btn-sm secondary" @click=${handleClose}>Close</button>`;
      break;
    }
    case "role": {
      const scopes = ["global", "state", "locality"];
      content = html`
        <div class="issues-page__resolve-role-content">
          ${(issue.states || []).length ? html`
            <p class="issues-page__modal-meta">
              Seen in:
              ${issue.states.map((s) => html`<span class="issues-page__state-badge">${s.toUpperCase()}</span> `)}
            </p>
          ` : null}

          <div class="issues-page__resolve-tabs">
            ${scopes.map((scope) => {
              const disabled = scope === "global" && !permissions.CONFIG_GLOBAL_WRITE;
              return html`
                <button
                  class="issues-page__resolve-tab${modalScope === scope ? " issues-page__resolve-tab--active" : ""}${disabled ? " issues-page__resolve-tab--disabled" : ""}"
                  ?disabled=${disabled}
                  @click=${() => { setModalScope(scope); setModalState((issue.states || [])[0] || ""); setModalLocality(""); }}
                >
                  ${scope.charAt(0).toUpperCase() + scope.slice(1)}
                  ${disabled ? html`<span class="issues-page__resolve-scope-hint">(admin only)</span>` : null}
                </button>
              `;
            })}
          </div>

          <div class="issues-page__resolve-tab-content">
            ${modalScope === "global" ? html`
              <p class="issues-page__modal-meta">Applies the fix to the global config — affects all jurisdictions.</p>
            ` : null}
            ${modalScope === "state" || modalScope === "locality" ? html`
              <label>
                State
                <select @change=${(e) => { setModalState(e.target.value); setModalLocality(""); }}>
                  ${(issue.states || []).map((s) => html`
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
                  ${(issue.jurisdictions || []).filter((j) => j.state === modalState).map((j) => html`
                    <option value=${j.locality} ?selected=${j.locality === modalLocality}>${j.locality || j.folder}</option>
                  `)}
                </select>
              </label>
            ` : null}
          </div>

          ${sourceSection}
        </div>
      `;
      footer = html`
        <button class="btn btn-sm secondary" @click=${handleClose}>Cancel</button>
        <button class="btn btn-sm" @click=${handleSubmit}>Open PR →</button>
      `;
      break;
    }
    default:
      return null;
  }

  return html`
    <civ-modal
      .title=${getModalTitle(modalType, issue)}
      .content=${content}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleClose }}
    ></civ-modal>
  `;
}

customElements.define("issues-resolve-modal", component(ResolveModal, { useShadowDOM: false, observedAttributes: ["details-only"] }));
