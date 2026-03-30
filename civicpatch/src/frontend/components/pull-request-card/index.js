import { html } from "lit-html";
import { component } from "haunted";
import { PULL_REQUEST_STATUS } from "./pull-request-status.js";
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

function diffStats(entry) {
  const existingMap = Object.fromEntries(
    (entry?.existing ?? []).map((p) => [p?.id, p]),
  );
  const proposedMap = Object.fromEntries(
    (entry?.proposed ?? []).map((p) => [p?.id, p]),
  );
  const allKeys = new Set([...Object.keys(existingMap), ...Object.keys(proposedMap)]);
  let added = 0, removed = 0, changed = 0;
  for (const key of allKeys) {
    const e = existingMap[key], p = proposedMap[key];
    if (!e) added++;
    else if (!p) removed++;
    else if (
      (e.office?.name ?? "") !== (p.office?.name ?? "") ||
      (e.office?.division_ocdid ?? "") !== (p.office?.division_ocdid ?? "")
    ) changed++;
  }
  return { added, removed, changed };
}

function PrCard({ entry, state }) {
  const stats = diffStats(entry);

  const renderCardContent = () => {
    if (state?.status === PULL_REQUEST_STATUS.MERGED) {
      return html`<div class="pr-card__content">Merged</div>`;
    }
    if (state?.status === PULL_REQUEST_STATUS.CLOSED) {
      return html`<div class="pr-card__content">Closed</div>`;
    }
    if (state?.status === PULL_REQUEST_STATUS.ERROR) {
      return html`<div class="pr-card__content">Error: ${state?.error}</div>`;
    }

    return html`<data-panel .entry=${entry}></data-panel>`;
  };

  return html`
    <div class="pr-card">
      ${PrTimestamp({ createdAt: entry?.created_at })}
      <pull-request-card-header
        .entry=${entry}
        .state=${state}
        .stats=${stats}
      ></pull-request-card-header>
      ${renderCardContent()}
    </div>
  `;
}

customElements.define("pr-card", component(PrCard, { useShadowDOM: false }));
