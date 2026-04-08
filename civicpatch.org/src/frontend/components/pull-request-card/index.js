import "./pr-card.css";
import { html } from "lit-html";
import { component } from "haunted";
import { PULL_REQUEST_STATUS } from "./pull-request-status.js";
import "./header.js";
import "./data-panel.js";
import "../diff-panel/diff-panel.js";

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

function PrCard({ entry, state, viewMode = "quick" }) {
  const stats = diffStats(entry);

  const renderCardContent = () => {
    if (state?.status === PULL_REQUEST_STATUS.CLOSED) {
      return html`<div class="pr-card__content">Closed</div>`;
    }
    if (state?.status === PULL_REQUEST_STATUS.ERROR) {
      return html`<div class="pr-card__content">Error: ${state?.error}</div>`;
    }

    if (viewMode === "detail") {
      return html`<civ-diff-panel
        .data=${{ existing: entry?.existing ?? [], proposed: entry?.proposed ?? [] }}
      ></civ-diff-panel>`;
    }
    return html`<data-panel .entry=${entry}></data-panel>`;
  };

  const isPublished = state?.status === PULL_REQUEST_STATUS.MERGED;
  const isPublishing = state?.status === PULL_REQUEST_STATUS.LOADING_MERGE;

  return html`
    <div class="pr-card">
      <pull-request-card-header
        .entry=${entry}
        .state=${state}
        .stats=${stats}
        .createdAt=${entry?.created_at}
      ></pull-request-card-header>
      ${renderCardContent()}
      ${isPublished ? html`<div class="pr-card__overlay pr-card__overlay--published"><span>Published.</span></div>` : null}
      ${isPublishing ? html`<div class="pr-card__overlay pr-card__overlay--publishing"><span>Publishing…</span></div>` : null}
    </div>
  `;
}

customElements.define("pr-card", component(PrCard, { useShadowDOM: false }));
