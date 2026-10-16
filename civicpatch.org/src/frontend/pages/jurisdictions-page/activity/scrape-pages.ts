// The pages one scrape read, and what happened to each.

import { component, useState, useEffect } from "haunted";
import { html, nothing } from "lit-html";
import { fetchScrapePages } from "../../../api.js";
import { dateStringToFriendly } from "../../../utils/date-utils.js";

// Mirrors PageOutcome in core/source_page_outcomes.py.
const READ = "read";
const UNCHANGED = "unchanged";
const NOT_ABOUT_OFFICIALS = "not_about_officials";
const EXTRACTION_FAILED = "extraction_failed";
const FAILED_TO_LOAD = "failed_to_load";

type PageOutcome =
  | typeof READ
  | typeof UNCHANGED
  | typeof NOT_ABOUT_OFFICIALS
  | typeof EXTRACTION_FAILED
  | typeof FAILED_TO_LOAD;

interface ScrapePage {
  source_url: string;
  outcome: PageOutcome;
  unchanged_since: string | null;
  organization_names: string[];
  people_count: number;
  markdown_url: string | null;
  html_url: string | null;
}

const OUTCOME_LABEL: Record<PageOutcome, string> = {
  [READ]: "read",
  [UNCHANGED]: "unchanged",
  [NOT_ABOUT_OFFICIALS]: "not about officials",
  [EXTRACTION_FAILED]: "extraction failed",
  [FAILED_TO_LOAD]: "failed to load",
};

// The timeline's own outcome pills: green worked, grey nothing to do, red a problem.
const OUTCOME_PILL: Record<PageOutcome, string> = {
  [READ]: "published",
  [UNCHANGED]: "unchanged",
  [NOT_ABOUT_OFFICIALS]: "cancelled",
  [EXTRACTION_FAILED]: "errored",
  [FAILED_TO_LOAD]: "errored",
};

const withoutScheme = (url: string) => url.replace(/^https?:\/\//, "");

const people = (count: number) => (count === 1 ? "1 person" : `${count} people`);

function describe(page: ScrapePage) {
  if (page.unchanged_since) {
    return `since ${dateStringToFriendly(page.unchanged_since)}, ${people(page.people_count)}`;
  }
  return page.outcome === READ ? people(page.people_count) : "";
}

function renderCachedCopies(page: ScrapePage) {
  if (!page.markdown_url && !page.html_url) return nothing;
  return html`
    <span class="tl-page__cached">
      ${page.markdown_url
        ? html`<a href=${page.markdown_url} target="_blank" rel="noopener noreferrer">markdown</a>`
        : nothing}
      ${page.html_url
        ? html`<a href=${page.html_url} target="_blank" rel="noopener noreferrer">html</a>`
        : nothing}
    </span>
  `;
}

function renderPage(page: ScrapePage) {
  return html`
    <li class="tl-page">
      <a
        class="tl-page__url"
        href=${page.source_url}
        target="_blank"
        rel="noopener noreferrer"
        >${withoutScheme(page.source_url)}</a
      >
      <span class="runs-pill runs-pill--${OUTCOME_PILL[page.outcome]}"
        >${OUTCOME_LABEL[page.outcome]}</span
      >
      <span class="tl-quiet">${describe(page)}</span>
      <span class="tl-page__organizations">${page.organization_names.join(", ")}</span>
      ${renderCachedCopies(page)}
    </li>
  `;
}

type ScrapePagesProps = { changesetId: string };

function CivScrapePages({ changesetId }: ScrapePagesProps) {
  const [pages, setPages] = useState<ScrapePage[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetchScrapePages(changesetId)
      .then((body) => setPages(body.data))
      .catch(() => setFailed(true));
  }, [changesetId]);

  if (failed) return html`<p class="tl-empty">Could not load the pages.</p>`;
  if (!pages) return html`<p class="tl-empty">Loading pages…</p>`;
  return html`<ul class="tl-pages">${pages.map(renderPage)}</ul>`;
}

customElements.define(
  "civ-scrape-pages",
  component(CivScrapePages as any, { useShadowDOM: false }),
);
