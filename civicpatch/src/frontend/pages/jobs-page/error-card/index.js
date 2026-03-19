import { html } from "lit-html";
import { component } from "haunted";
import { jurisdictionOcdidToFriendly } from "../ocdid-utils.js";
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

  return html`
    <div class="error-card">
      <div class="error-card__header">
        <div class="header-item-left">
          <civ-badge .label=${name}></civ-badge>
          <span class="error-card__request-id">${job?.request_id}</span>
          <span class="error-card__state">error</span>
        </div>
        <div class="header-item-right">
          <a
            class="error-card__link"
            href="/jurisdictions?jurisdiction_ocdid=${job?.jurisdiction_ocdid}"
            target="_blank"
            rel="noopener"
          >Detail</a>
        </div>
      </div>
      ${updatedAt ? html`<div class="error-card__meta">last updated ${updatedAt}</div>` : ""}
      <div class="error-card__body">
        <span class="error-card__placeholder">No error details available.</span>
      </div>
    </div>
  `;
}

customElements.define("error-card", component(ErrorCard, { useShadowDOM: false }));
