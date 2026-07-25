import "./jurisdiction-sidebar.css";
import { component } from "haunted";
import { html } from "lit-html";
import "./jurisdiction-detail.js";

function JurisdictionSidebar({
  jurisdictionData,
  onScrapeClick,
  canStartScrape,
  isJobRunning,
  hasOpenPr,
  scrapeError,
  canEdit,
  onSave,
}) {
  if (!jurisdictionData) {
    return html`<p>Loading jurisdiction data...</p>`;
  }

  return html`
    <div>
      <civ-jurisdiction-detail .data=${jurisdictionData.data} .canEdit=${canEdit} .onSave=${onSave}></civ-jurisdiction-detail>

      ${canStartScrape ? html`
        <button
          @click=${onScrapeClick}
          class="primary jurisdiction-sidebar__scrape-btn btn-gradient"
          ?disabled=${isJobRunning || hasOpenPr}
        >
          Scrape for Jurisdiction
        </button>
        ${hasOpenPr ? html`<p class="jurisdiction-sidebar__scrape-hint">An open pull request already exists for this jurisdiction.</p>` : null}
        ${scrapeError ? html`<p class="jurisdiction-sidebar__scrape-error">${scrapeError}</p>` : null}
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
