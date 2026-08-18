// Breadcrumb, name, scrape status, and the page's actions.
//
// Pure render — every piece of state arrives as a prop, and the one action the
// header owns (re-scrape) is a callback the page supplies.

import { html, nothing } from "lit-html";
import { dateStringToFriendly } from "../../utils/date-utils.js";
import { jurisdictionOcdidToState } from "../../components/ocdid-utils.js";

export interface JurisdictionHeaderProps {
  name: string;
  ocdid: string;
  isScraped: boolean;
  publishedAt?: string | null;
  canStartScrape: boolean;
  isScrapeBlocked: boolean;
  isRunInProgress: boolean;
  onScrapeClick: () => void;
}

function issueUrl(name: string, ocdid: string) {
  const title = encodeURIComponent(`[Jurisdiction issue] ${name}`);
  const body = encodeURIComponent(
    `**Jurisdiction:** ${name}\n**OCD ID:** ${ocdid}\n\n**Issue type** (check all that apply):\n- [ ] Wrong website\n- [ ] Stale or incorrect data\n- [ ] Other\n\n**Description:**\n`,
  );
  return `https://github.com/CivicPatch/open-data/issues/new?template=jurisdiction_issue.md&title=${title}&body=${body}&labels=data-quality`;
}

function renderBreadcrumb(name: string, ocdid: string) {
  const state = jurisdictionOcdidToState(ocdid);
  if (!state) return nothing;
  return html`
    <nav class="jurisdiction-page__breadcrumb" aria-label="Breadcrumb">
      <a href="/${state}/local">${state.toUpperCase()} municipalities</a>
      <span aria-hidden="true">/</span>
      <span aria-current="page">${name}</span>
    </nav>
  `;
}

export function renderJurisdictionHeader(props: JurisdictionHeaderProps) {
  const {
    name,
    ocdid,
    isScraped,
    publishedAt,
    canStartScrape,
    isScrapeBlocked,
    isRunInProgress,
    onScrapeClick,
  } = props;

  return html`
    ${renderBreadcrumb(name, ocdid)}

    <div class="jurisdiction-page__title-row">
      <div class="jurisdiction-page__heading">
        <h1 class="jurisdiction-page__h1">${name}</h1>
        <span
          class="jurisdiction-status ${isScraped ? "jurisdiction-status--scraped" : ""}"
        >
          <span class="jurisdiction-status__dot"></span>
          ${isScraped ? "Scraped" : "Unscraped"}
        </span>
        ${isScraped && publishedAt
          ? html`<span class="jurisdiction-page__published">
              Published ${dateStringToFriendly(publishedAt)}
            </span>`
          : nothing}
      </div>

      <div class="jurisdiction-page__actions">
        ${name && ocdid
          ? html`<a
              href=${issueUrl(name, ocdid)}
              target="_blank"
              rel="noopener noreferrer"
              style="font-size: var(--text-sm); white-space: nowrap;"
            >
              <i class="fa-solid fa-flag"></i> Report an issue
            </a>`
          : nothing}
        ${canStartScrape
          ? html`<button
              class="btn-primary"
              ?disabled=${isRunInProgress || isScrapeBlocked}
              @click=${onScrapeClick}
            >
              <i class="fa-solid fa-rotate ${isRunInProgress ? "fa-spin" : ""}"></i>
              ${isRunInProgress ? "Scraping…" : "Re-scrape"}
            </button>`
          : nothing}
      </div>
    </div>

    <hr class="jurisdiction-page__hairline" />
  `;
}
