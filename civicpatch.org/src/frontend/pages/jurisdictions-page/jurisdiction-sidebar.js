import "./jurisdiction-sidebar.css";
import { component } from "haunted";
import { html } from "lit-html";
import "./jurisdiction-detail.js";

function buildIssueUrl(name, ocdid) {
  const title = encodeURIComponent(`[Jurisdiction issue] ${name}`);
  const body = encodeURIComponent(
    `**Jurisdiction:** ${name}\n**OCD ID:** ${ocdid}\n\n**Issue type** (check all that apply):\n- [ ] PDF (site serves a PDF instead of an HTML page)\n- [ ] No website\n- [ ] Authentication required\n- [ ] JavaScript-heavy (page doesn't render without JS)\n- [ ] Stale or incorrect data\n- [ ] Other\n\n**Description:**\n`
  );
  return `https://github.com/CivicPatch/open-data/issues/new?template=jurisdiction_issue.md&title=${title}&body=${body}&labels=data-quality`;
}

function JurisdictionSidebar({
  jurisdictionData,
  onScrapeClick,
  canStartScrape,
  isJobRunning,
  onSave,
}) {
  if (!jurisdictionData) {
    return html`<p>Loading jurisdiction data...</p>`;
  }

  const issueUrl = buildIssueUrl(jurisdictionData.data.name, jurisdictionData.data.id);

  return html`
    <div>
      <civ-jurisdiction-detail .data=${jurisdictionData.data} .onSave=${onSave}></civ-jurisdiction-detail>

      ${canStartScrape ? html`
        <button
          @click=${onScrapeClick}
          class="primary jurisdiction-sidebar__scrape-btn btn-gradient"
          ?disabled=${isJobRunning}
        >
          Scrape for Jurisdiction
        </button>
      ` : null}

      <a href=${issueUrl} target="_blank" rel="noopener noreferrer">Report an issue</a>
    </div>
  `;
}

customElements.define(
  "civ-jurisdiction-sidebar",
  component(JurisdictionSidebar, {
    useShadowDOM: false,
  }),
);
