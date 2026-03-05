import { component } from "haunted";
import { html } from "lit-html";

function JurisdictionHeader({ name, scrapeStatus }) {
  return html`
    <style>
      .jurisdiction-title {
        position: relative;
        z-index: 1;
        color: rgb(var(--catppuccin-base));
        padding: 0.5rem 1.5rem;
      }

      .jurisdiction-title::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(var(--catppuccin-sapphire), 1.0);
        transform: skew(-20deg);
        z-index: -1;
      }
    </style>
    <header>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <h2 class="jurisdiction-title" style="margin-bottom: 0">${name}</h2>
        <span style="font-size: 1.75rem">Status: ${scrapeStatus}</span>
      </div>
    </header>
  `;
}

customElements.define(
  "civ-jurisdiction-header",
  component(JurisdictionHeader, {
    useShadowDOM: false,
  }),
);
