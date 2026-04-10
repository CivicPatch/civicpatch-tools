import "./error-card.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { jurisdictionOcdidToFriendly } from "../../../components/ocdid-utils.js";
import { JOB_STATUS } from "../../../components/job-status.js";
import "../../../components/badge/badge.js";
import "../../../components/basic/modal.js";

function ErrorCard({ job }) {
  const name = job?.jurisdiction_name || jurisdictionOcdidToFriendly(job?.jurisdiction_ocdid);
  const updatedAt = job?.updated_at
    ? new Date(job.updated_at).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : null;

  const [logOpen, setLogOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("log");

  const isPaused = job?.status === JOB_STATUS.PAUSED;

  const handleResolve = (el) => {
    el.currentTarget.dispatchEvent(new CustomEvent("resolve-error", {
      bubbles: true,
      detail: { job },
    }));
  };

  const handleResume = (el) => {
    el.currentTarget.dispatchEvent(new CustomEvent("resume-job", {
      bubbles: true,
      detail: { job },
    }));
  };

  const handleLogClick = () => {
    setActiveTab("log");
    setLogOpen(true);
  };

  const tabs = [
    { id: "log", label: "Log" },
    { id: "context", label: "Context" },
    { id: "cache", label: "Cache" },
  ];

  const tabUrls = {
    log: job?.workflow_log_url,
    context: job?.workflow_context_url,
    cache: job?.cache_url,
  };

  const modalContent = html`
    <div class="error-card__modal-content">
      <div class="error-card__tabs">
        ${tabs.map(tab => html`
          <button
            class="error-card__tab ${activeTab === tab.id ? "error-card__tab--active" : ""}"
            @click=${() => setActiveTab(tab.id)}
          >${tab.label}</button>
        `)}
      </div>
      <div class="error-card__tab-body">
        ${activeTab === "cache"
          ? html`<div class="error-card__cache-link">
              <a href=${tabUrls.cache} target="_blank" rel="noopener">${tabUrls.cache}</a>
            </div>`
          : html`<iframe
              class="error-card__log"
              src=${logOpen ? (tabUrls[activeTab] || "") : ""}
              title=${activeTab}
            ></iframe>`
        }
      </div>
    </div>
  `;

  return html`
    <div class="error-card">
      <div class="error-card__header">
        <div class="header-item-left">
          <civ-badge .label=${name}></civ-badge>
          <span class="error-card__request-id">${job?.request_id}</span>
          <span
            class="error-card__state error-card__state--${isPaused ? "paused" : "error"} ${job?.workflow_log_url ? "error-card__state--clickable" : ""}"
            @click=${job?.workflow_log_url ? handleLogClick : null}
          >${isPaused ? "paused" : "error"}</span>
          <a
            class="error-card__link"
            href="/${job?.jurisdiction_path}"
            target="_blank"
            rel="noopener"
          >Detail</a>
        </div>
        <div class="header-item-right">
          ${isPaused
            ? html`<button class="btn-sm" @click=${handleResume}>Resume</button>`
            : html`<button class="btn-sm" @click=${handleResolve}>Resolve</button>`
          }
        </div>
      </div>
      ${updatedAt ? html`<div class="error-card__meta">last updated ${updatedAt}</div>` : ""}
      ${job?.workflow_log_url ? html`
        <civ-modal
          .title=${"Pipeline Logs"}
          .content=${modalContent}
          .modalProps=${{ open: logOpen, onClose: () => setLogOpen(false), closeOnBackdropClick: true }}
        ></civ-modal>
      ` : ""}
    </div>
  `;
}

customElements.define("error-card", component(ErrorCard, { useShadowDOM: false }));
