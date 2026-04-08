import "./civ-tab-bar.css";
import { html, component } from "haunted";

function CivTabBar({ tabs = [], selectedIndex = 0, onTabClick }) {
  return html`
    <div class="civ-tab-bar">
      ${tabs.map(({ label, colorClass }, idx) => html`
        <button
          class="civ-tab ${colorClass ?? ""} ${selectedIndex === idx ? "civ-tab--active" : ""}"
          @click=${() => onTabClick?.(idx)}
        >${label}</button>
      `)}
    </div>
  `;
}

customElements.define("civ-tab-bar", component(CivTabBar, { useShadowDOM: false }));
