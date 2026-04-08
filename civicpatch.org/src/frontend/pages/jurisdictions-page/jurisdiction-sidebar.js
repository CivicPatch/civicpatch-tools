import "./jurisdiction-sidebar.css";
import { component } from "haunted";
import { html } from "lit-html";
import "./jurisdiction-detail.js";

function JurisdictionSidebar({
  jurisdictionData,
  onScrapeClick,
  canStartScrape
}) {
  if (!jurisdictionData) {
    return html`<p>Loading jurisdiction data...</p>`;
  }

  return html`
    <div>
      <civ-jurisdiction-detail .data=${jurisdictionData.data}></civ-jurisdiction-detail>

      ${canStartScrape ? html`
        <button
          @click=${onScrapeClick}
          class="primary jurisdiction-sidebar__scrape-btn btn-gradient"
        >
          Scrape for Jurisdiction
        </button>
      ` : null}
    </div>
  `;
}

customElements.define(
  "civ-jurisdiction-sidebar",
  component(JurisdictionSidebar, {
    useShadowDOM: false,
  }),
);
