// Breadcrumb, name, scrape status, and the page's actions.
//
// Pure render — every piece of state arrives as a prop, and the one action the
// header owns (re-scrape) is a callback the page supplies.

import { html, nothing } from "lit-html";
import { dateStringToFriendly } from "../../utils/date-utils.js";
import { jurisdictionOcdidToState } from "../../components/ocdid-utils.js";
import { IN_PROGRESS_ANCHOR } from "./history/history-routes.js";

// Mirrors FRESH_SINCE_SQL in database/jurisdictions.py, which is what actually decides
// whether a jurisdiction is offered up for re-scraping. Two copies of one number: if the
// server's window moves, this label goes on disagreeing with the scheduler until it follows.
const FRESH_DAYS = 90;

// Four states, not two. "Scraped" collapsed three of them into one word: a place with no site
// to scrape, a place with a site but nothing collected, and a place whose roster is years old
// all read the same.
const STATUS = Object.freeze({
  UP_TO_DATE: { label: "Up to date", modifier: "fresh" },
  STALE: { label: "Stale", modifier: "stale" },
  NO_DATA: { label: "No data", modifier: "empty" },
  UNTRACKED: { label: "Untracked", modifier: "untracked" },
});

const daysSince = (iso: string) =>
  (Date.now() - new Date(iso).getTime()) / 86_400_000;

// An inactive jurisdiction never reaches this page — `get_jurisdiction` filters on it and the
// route 404s — so untracked here means the one remaining case: no site to scrape.
function statusOf(hasUrl: boolean, isScraped: boolean, publishedAt?: string | null) {
  if (!hasUrl) return STATUS.UNTRACKED;
  if (!isScraped) return STATUS.NO_DATA;
  if (!publishedAt || daysSince(publishedAt) > FRESH_DAYS) return STATUS.STALE;
  return STATUS.UP_TO_DATE;
}

export interface JurisdictionHeaderProps {
  name: string;
  ocdid: string;
  isScraped: boolean;
  hasUrl: boolean;
  publishedAt?: string | null;
  historyHref: string;
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
    hasUrl,
    publishedAt,
    historyHref,
    canStartScrape,
    isScrapeBlocked,
    isRunInProgress,
    onScrapeClick,
  } = props;

  const status = statusOf(hasUrl, isScraped, publishedAt);

  return html`
    ${renderBreadcrumb(name, ocdid)}

    <div class="jurisdiction-page__title-row">
      <div class="jurisdiction-page__heading">
        <h1 class="jurisdiction-page__h1">${name}</h1>
        <span class="jurisdiction-status jurisdiction-status--${status.modifier}">
          <span class="jurisdiction-status__dot"></span>
          ${status.label}${publishedAt
            ? html` — ${dateStringToFriendly(publishedAt)}`
            : nothing}
        </span>
        ${isRunInProgress
          ? html`<a
              class="jurisdiction-status jurisdiction-status--running"
              href="${historyHref}#${IN_PROGRESS_ANCHOR}"
            >
              <span class="jurisdiction-status__dot"></span>
              Scrape running →
            </a>`
          : nothing}
      </div>

      <div class="jurisdiction-page__actions">
        <a href=${historyHref} style="font-size: var(--text-sm); white-space: nowrap;">
          <i class="fa-solid fa-clock-rotate-left"></i> History
        </a>
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
