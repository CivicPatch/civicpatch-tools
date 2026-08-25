import "./publish-log.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { REVIEW_ACTION } from "../pull-request-card/review-action.js";

function PublishLog({ entries = [] }) {
  const [collapsed, setCollapsed] = useState(false);

  if (!entries.length) return null;

  const inFlight = entries.filter((e) => e.status === REVIEW_ACTION.APPROVING).length;

  return html`
    <div class="publish-log">
      <div class="publish-log__header">
        <span class="publish-log__title">Publishing${inFlight ? html` <span class="civ-badge civ-badge--primary">${inFlight}</span>` : ""}</span>
        <button
          class="publish-log__toggle"
          @click=${() => setCollapsed((c) => !c)}
        >${collapsed ? "show" : "hide"}</button>
      </div>
      ${collapsed ? null : html`
        <ul class="publish-log__list">
          ${entries.map((e) => {
            let statusEl = html`<span class="publish-log__spinner"></span>`;
            let modifierClass = "";
            if (e.status === REVIEW_ACTION.APPROVED) {
              statusEl = html`<span class="publish-log__status">✓</span>`;
              modifierClass = "publish-log__item--done";
            } else if (e.status === REVIEW_ACTION.ERROR) {
              statusEl = html`<span class="publish-log__status">✕</span>`;
              modifierClass = "publish-log__item--error";
            }
            return html`
              <li class="publish-log__item ${modifierClass}">
                <span class="publish-log__name">${e.jurisdiction_name}</span>
                <span class="publish-log__pr">#${e.pull_request_number}</span>
                ${statusEl}
              </li>
            `;
          })}
        </ul>
      `}
    </div>
  `;
}

customElements.define("civ-publish-log", component(PublishLog, { useShadowDOM: false }));
