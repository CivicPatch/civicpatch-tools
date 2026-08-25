import "./review-log.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { REVIEW_ACTION } from "../review-card/review-action.js";

function ReviewLog({ entries = [] }) {
  const [collapsed, setCollapsed] = useState(false);

  if (!entries.length) return null;

  const inFlight = entries.filter((e) => e.status === REVIEW_ACTION.APPROVING).length;

  return html`
    <div class="review-log">
      <div class="review-log__header">
        <span class="review-log__title">Approving${inFlight ? html` <span class="civ-badge civ-badge--primary">${inFlight}</span>` : ""}</span>
        <button
          class="review-log__toggle"
          @click=${() => setCollapsed((c) => !c)}
        >${collapsed ? "show" : "hide"}</button>
      </div>
      ${collapsed ? null : html`
        <ul class="review-log__list">
          ${entries.map((e) => {
            let statusEl = html`<span class="review-log__spinner"></span>`;
            let modifierClass = "";
            if (e.status === REVIEW_ACTION.APPROVED) {
              statusEl = html`<span class="review-log__status">✓</span>`;
              modifierClass = "review-log__item--done";
            } else if (e.status === REVIEW_ACTION.ERROR) {
              statusEl = html`<span class="review-log__status">✕</span>`;
              modifierClass = "review-log__item--error";
            }
            return html`
              <li class="review-log__item ${modifierClass}">
                <span class="review-log__name">${e.jurisdiction_name}</span>
                ${statusEl}
              </li>
            `;
          })}
        </ul>
      `}
    </div>
  `;
}

customElements.define("civ-review-log", component(ReviewLog, { useShadowDOM: false }));
