import { html } from "lit-html";
import { component, useState } from "haunted";
import { PULL_REQUEST_STATUS } from "../index.js";
import "./header.js";
import "./data-panel.js";

const PrTimestamp = ({ createdAt }) =>
  createdAt
    ? html`<div class="pr-card__meta">
        created
        ${new Date(createdAt).toLocaleDateString("en-US", {
          year: "numeric",
          month: "short",
          day: "numeric",
        })}
      </div>`
    : "";

function PrCard({ pr, data, state }) {
  const renderCardContent = () => {
    if (state?.status === PULL_REQUEST_STATUS.MERGED) {
      return html`<div class="pr-card__content">Merged</div>`;
    }
    if (state?.status === PULL_REQUEST_STATUS.ERROR) {
      return html`<div class="pr-card__content">Error: ${state?.error}</div>`;
    }

    return html`<data-panel .data=${data}></data-panel>`;
  };

  return html`
    <div class="pr-card">
      ${PrTimestamp({ createdAt: pr?.created_at })}
      <pull-request-card-header
        .pr=${pr}
        .state=${state}
      ></pull-request-card-header>
      ${renderCardContent()}
    </div>
  `;
}

customElements.define("pr-card", component(PrCard, { useShadowDOM: false }));
