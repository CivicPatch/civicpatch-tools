import "./review-card.css";
import { html } from "lit-html";
import { component } from "haunted";
import { REVIEW_ACTION } from "./review-action.js";
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

function ReviewCard({ entry, state, viewMode = "quick" }) {
  const stats = diffStats(entry);

  const renderCardContent = () => {
    if (state?.status === REVIEW_ACTION.REJECTED) {
      return html`<div class="review-card__content">Closed</div>`;
    }
    if (state?.status === REVIEW_ACTION.ERROR) {
      return html`<div class="review-card__content">Error: ${state?.error}</div>`;
    }

    if (viewMode === "detail") {
      return html`<civ-diff-panel
        .data=${{ existing: entry?.existing ?? [], proposed: entry?.proposed ?? [] }}
      ></civ-diff-panel>`;
    }
    return html`<data-panel .entry=${entry}></data-panel>`;
  };

  const isPublished = state?.status === REVIEW_ACTION.APPROVED;
  const isPublishing = state?.status === REVIEW_ACTION.APPROVING;

  return html`
    <div class="review-card">
      <review-card-header
        .entry=${entry}
        .state=${state}
        .stats=${stats}
        .createdAt=${entry?.created_at}
      ></review-card-header>
      ${renderCardContent()}
      ${isPublished ? html`<div class="review-card__overlay review-card__overlay--published"><span>Published.</span></div>` : null}
      ${isPublishing ? html`<div class="review-card__overlay review-card__overlay--publishing"><span>Publishing…</span></div>` : null}
    </div>
  `;
}

customElements.define("review-card", component(ReviewCard, { useShadowDOM: false }));
