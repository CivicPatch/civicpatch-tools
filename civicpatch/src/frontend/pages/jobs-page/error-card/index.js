import { html } from "lit-html";
import { component, useState } from "haunted";
import { createRef, ref } from "lit-html/directives/ref.js";
import { jurisdictionOcdidToFriendly } from "../../../components/ocdid-utils.js";
import "../../../components/badge/badge.js";

function ErrorCard({ job }) {
  const name = job?.jurisdiction_name || jurisdictionOcdidToFriendly(job?.jurisdiction_ocdid);
  const updatedAt = job?.updated_at
    ? new Date(job.updated_at).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : null;
  const logPopoverRef = createRef();
  const [logLoaded, setLogLoaded] = useState(false);

  const handleResolve = (el) => {
    el.currentTarget.dispatchEvent(new CustomEvent("resolve-error", {
      bubbles: true,
      detail: { job },
    }));
  };

  const handleLogClick = () => {
    setLogLoaded(true);
    logPopoverRef.value?.showPopover();
  };

  return html`
    <div class="error-card">
      <div class="error-card__header">
        <div class="header-item-left">
          <civ-badge .label=${name}></civ-badge>
          <span class="error-card__request-id">${job?.request_id}</span>
          <span
            class="error-card__state ${job?.workflow_log_url ? "error-card__state--clickable" : ""}"
            @click=${job?.workflow_log_url ? handleLogClick : null}
          >error</span>
          ${job?.workflow_log_url ? html`
            <div popover ${ref(logPopoverRef)} class="error-card__log-popover">
              <iframe
                class="error-card__log"
                src=${logLoaded ? job.workflow_log_url : ""}
                title="Workflow log"
              ></iframe>
            </div>
          ` : ""}
          <a
            class="error-card__link"
            href="/jurisdictions?jurisdiction_ocdid=${job?.jurisdiction_ocdid}"
            target="_blank"
            rel="noopener"
          >Detail</a>
        </div>
        <div class="header-item-right">
          <button class="btn-sm" @click=${handleResolve}>Resolve</button>
        </div>
      </div>
      ${updatedAt ? html`<div class="error-card__meta">last updated ${updatedAt}</div>` : ""}
    </div>
  `;
}

customElements.define("error-card", component(ErrorCard, { useShadowDOM: false }));
