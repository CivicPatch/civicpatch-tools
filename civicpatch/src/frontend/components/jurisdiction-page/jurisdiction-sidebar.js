import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import "../scrape-history/scrape-history-list.js";
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
    fetch(`/api/api_proxy/jurisdictions/history?jurisdiction_ocdid=${encodeURIComponent(jurisdiction_ocdid)}`, {
      credentials: "include",
    })
      .then(r => r.json())
      .then(setHistory)
      .catch(() => setHistory(null));
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
