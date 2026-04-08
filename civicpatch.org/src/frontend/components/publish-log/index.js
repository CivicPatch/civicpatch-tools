import "./publish-log.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { PULL_REQUEST_STATUS } from "../pull-request-card/pull-request-status.js";

function PublishLog({ entries = [] }) {
  const [collapsed, setCollapsed] = useState(false);

  if (!entries.length) return null;

  const inFlight = entries.filter((e) => e.status === PULL_REQUEST_STATUS.LOADING_MERGE).length;

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
            if (e.status === PULL_REQUEST_STATUS.MERGED) {
              statusEl = html`<span class="publish-log__status">✓</span>`;
              modifierClass = "publish-log__item--done";
            } else if (e.status === PULL_REQUEST_STATUS.ERROR) {
              statusEl = html`<span class="publish-log__status">✕</span>`;
              modifierClass = "publish-log__item--error";
            }
            return html`
              <li class="publish-log__item ${modifierClass}">
                <span class="publish-log__name">${e.jurisdictionName}</span>
                <span class="publish-log__pr">#${e.pullRequestNumber}</span>
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
