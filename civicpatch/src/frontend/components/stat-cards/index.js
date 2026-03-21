import { html } from "lit-html";
import { component, useState } from "haunted";

// Each stat: { key, label, value, sub, copyText, description? }
function StatCards({ stats }) {
  const [copied, setCopied] = useState(null);

  const copy = (key, text) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 1500);
  };

  return html`
    <div class="stat-cards">
      ${(stats || []).map((stat) => html`
        <button
          class="stat-cards__card"
          @click=${() => copy(stat.key, stat.copyText)}
          data-tooltip=${stat.description || null}
          data-placement="bottom"
        >
          <div class="stat-cards__label">${stat.label}</div>
          <div class="stat-cards__value">${stat.value}</div>
          <div class="stat-cards__sub">${stat.sub}</div>
          <i class="stat-cards__copy-icon ${copied === stat.key ? "stat-cards__copy-icon--copied fa-solid fa-check" : "fa-regular fa-copy"}"></i>
        </button>
      `)}
    </div>
  `;
}

customElements.define("stat-cards", component(StatCards, { useShadowDOM: false }));
