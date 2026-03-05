import { component } from "haunted";
import { html } from "lit-html";
import "../scrape-history/scrape-history-list.js";
import "./jurisdiction-detail.js";

function JurisdictionSidebar({ 
  jurisdictionData, 
  history, 
  jobStatus, 
  isConnected, 
  sseError,
  onScrapeClick,
  canStartScrape 
}) {
  if (!jurisdictionData) {
    return html`<p>Loading jurisdiction data...</p>`;
  }

  return html`
    <div>
      <civ-jurisdiction-detail .data=${jurisdictionData.data}></civ-jurisdiction-detail>
      
      <hr />
      
      <civ-scrape-history-list
        .history=${history}
        .jobStatus=${jobStatus}
        .isConnected=${isConnected}
        .sseError=${sseError}
      ></civ-scrape-history-list>

      <button
        @click=${onScrapeClick}
        ?disabled=${!canStartScrape}
        class="primary"
      >
        Scrape Data for Jurisdiction
      </button>
    </div>
  `;
}

customElements.define(
  "civ-jurisdiction-sidebar",
  component(JurisdictionSidebar, {
    useShadowDOM: false,
  }),
);
