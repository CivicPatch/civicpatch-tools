import "./badge.css";
import { html } from "lit-html";
import { component } from "haunted";

function CivBadge({ label, variant = "primary", popoverText, popoverId }) {
  if (popoverText !== undefined && popoverId) {
    return html`
      <button
        class="civ-badge civ-badge--${variant}"
        popovertarget=${popoverId}
        popovertargetaction="toggle"
      >${label}</button>
      <div id=${popoverId} popover class="civ-badge__popover">${popoverText}</div>
    `;
  }
  return html`<span class="civ-badge civ-badge--${variant}">${label}</span>`;
}

customElements.define("civ-badge", component(CivBadge, { useShadowDOM: false }));
