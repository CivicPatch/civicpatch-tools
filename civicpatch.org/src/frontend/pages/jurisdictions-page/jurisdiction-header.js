import { component } from "haunted";
import { html } from "lit-html";
import "../../components/badge/badge.js";

function buildIssueUrl(name, ocdid) {
  const title = encodeURIComponent(`[Jurisdiction issue] ${name}`);
  const body = encodeURIComponent(
    `**Jurisdiction:** ${name}\n**OCD ID:** ${ocdid}\n\n**Issue type** (check all that apply):\n- [ ] Wrong website\n- [ ] Stale or incorrect data\n- [ ] Other\n\n**Description:**\n`
  );
  return `https://github.com/CivicPatch/open-data/issues/new?template=jurisdiction_issue.md&title=${title}&body=${body}&labels=data-quality`;
}

function JurisdictionHeader({ name, scrapeStatus, details, ocdid }) {
  const isScraped = scrapeStatus === "Scraped";

  return html`
    <style>
      .jh-wrap {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
      }

      .jh-name {
        position: relative;
        z-index: 1;
        color: var(--pico-primary-inverse);
        padding: 0.5rem 1.5rem;
        margin: 0;
      }
      .jh-name::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: var(--pico-primary);
        transform: skew(-20deg);
        z-index: -1;
      }

      .jh-status {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.8125rem;
        font-weight: 600;
        padding: 0.25rem 0.65rem;
        border-radius: 2rem;
        white-space: nowrap;
        background: ${isScraped ? 'var(--pico-ins-background)' : 'var(--pico-muted-background)'};
        color: ${isScraped ? 'var(--pico-ins-color)' : 'var(--pico-muted-color)'};
      }
      .jh-status-dot {
        width: 0.4rem;
        height: 0.4rem;
        border-radius: 50%;
        background: currentColor;
        flex-shrink: 0;
      }
    </style>

    <header>
      <div class="jh-wrap">
        <div style="display: flex; align-items: center; gap: 0.6rem;">
          <h2 class="jh-name">${name}</h2>
        </div>
        <div style="display: flex; align-items: center; gap: 1rem;">
          <span class="jh-status">
            <span class="jh-status-dot"></span>
            ${scrapeStatus}
          </span>
          ${name && ocdid ? html`<a href=${buildIssueUrl(name, ocdid)} target="_blank" rel="noopener noreferrer" style="font-size: 0.8125rem; white-space: nowrap;"><i class="fa-regular fa-flag"></i> Report an issue</a>` : null}
        </div>
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