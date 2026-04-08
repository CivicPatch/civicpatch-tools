import { html } from "lit-html";
import { component, useState } from "haunted";

// Each stat: { key, label, value, sub, copyText?, description? }
// copyText is optional — omit it to render a plain non-interactive card
function StatCards({ stats }) {
  const [copied, setCopied] = useState(null);

  const copy = (key, text) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 1500);
  };

  return html`
    <div class="stat-cards">
      ${(stats || []).map((stat) => stat.copyText ? html`
        <button
          class="stat-cards__card"
          @click=${() => copy(stat.key, stat.copyText)}
          data-tooltip=${stat.description || stat.sub || null}
          data-placement=${stat.description || stat.sub ? "bottom" : null}
        >
          <div class="stat-cards__label">${stat.label}</div>
          <div class="stat-cards__value">${stat.value}</div>
          <div class="stat-cards__sub">${stat.sub}</div>
          <i class="stat-cards__copy-icon ${copied === stat.key ? "stat-cards__copy-icon--copied fa-solid fa-check" : "fa-regular fa-copy"}"></i>
        </button>
      ` : html`
        <div class="stat-cards__card">
          <div class="stat-cards__label">${stat.label}</div>
          <div class="stat-cards__value">${stat.value}</div>
          <div class="stat-cards__sub">${stat.sub}</div>
        </div>
      `)}
    </div>
  `;
}

customElements.define("stat-cards", component(StatCards, { useShadowDOM: false }));
