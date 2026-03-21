import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { fetchJurisdictionHistory } from "../../api.js";
import "../../components/scrape-history/scrape-history-list.js";
import "./jurisdiction-detail.js";

function JurisdictionSidebar({
  jurisdictionData,
  jurisdiction_ocdid,
  jobStatus,
  isConnected,
  sseError,
  onScrapeClick,
  canStartScrape
}) {
  const [history, setHistory] = useState(null);

  useEffect(() => {
    if (!jurisdiction_ocdid) return;
    async function loadHistory() {
      try {
        const data = await fetchJurisdictionHistory(jurisdiction_ocdid);
        setHistory(data);
      } catch {
        setHistory(null);
      }
    }
    loadHistory();
  }, [jurisdiction_ocdid]);

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

      ${canStartScrape ? html`
        <button
          @click=${onScrapeClick}
          class="primary jurisdiction-sidebar__scrape-btn"
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
