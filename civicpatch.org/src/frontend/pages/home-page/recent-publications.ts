import { html } from "lit-html";
import "../../components/panel/panel.css";
import "./recent-publications.css";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";
import { shortenIfUuid } from "../../components/username-utils.js";
import type { RecentPublication } from "./use-recent-publications.ts";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

// Every publish writes the same activity type regardless of what actually produced it (a
// scrape a reviewer approved, a maintainer's hand edit, a rollback) — `kind` is the only
// column that tells them apart, so the verb comes from it rather than being hardcoded.
const KIND_VERBS: Record<string, string> = {
  scrape: "published a review of",
  people_edit: "edited",
  sheet_import: "imported data for",
  jurisdiction_edit: "edited",
  rollback: "rolled back changes to",
};

export function verbFor(kind: string | null): string {
  return (kind && KIND_VERBS[kind]) ?? "updated";
}

// The DB already collapses same-day/same-town publishes into one row — the actor's own
// name carries the sentence, so this is only the trailing count when there's more than one.
export function reviewCountSuffix(review_count: number): string {
  return review_count > 1 ? `(${review_count} updates)` : "";
}

export function renderRecentPublications({
  publications,
  canViewProfiles,
}: {
  publications: RecentPublication[];
  canViewProfiles: boolean;
}) {
  if (publications.length === 0) return "";

  return html`
    <div class="panel recent-publications">
      <div class="panel__cap">
        <b>recently published</b>
      </div>
      <div class="recent-publications__list">
        ${publications.map(
          (pub) => html`
            <div class="recent-publications__row">
              <span class="recent-publications__at">${formatDate(pub.created_at)}</span>
              <span class="recent-publications__body">
                ${canViewProfiles
                  ? html`<a href="/~${pub.author_name}">${shortenIfUuid(pub.author_name)}</a>`
                  : shortenIfUuid(pub.author_name)}
                <em class="recent-publications__verb">${verbFor(pub.kind)}</em>
                <a href="/${jurisdictionOcdidToPath(pub.jurisdiction_ocdid)}"
                  >${pub.jurisdiction_name}</a
                >
                <span class="recent-publications__meta">${pub.state ?? ""}</span>
                ${reviewCountSuffix(pub.review_count)
                  ? html`<span class="recent-publications__meta"
                      >${reviewCountSuffix(pub.review_count)}</span
                    >`
                  : ""}
                ${pub.commit_url
                  ? html`<a
                      class="recent-publications__meta"
                      href=${pub.commit_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      >commit</a
                    >`
                  : ""}
              </span>
            </div>
          `,
        )}
      </div>
    </div>
  `;
}
