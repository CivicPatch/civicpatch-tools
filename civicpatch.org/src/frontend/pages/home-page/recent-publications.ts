import { html } from "lit-html";
import "../../components/panel/panel.css";
import "./recent-publications.css";
import {
  jurisdictionOcdidToPath,
  stateNameForCode,
} from "../../components/ocdid-utils.js";
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
//
// Passive, not "X imported data for" — the jurisdiction is the subject of the sentence
// (no author here, see schemas/activity.py::PublicPublication), so the verb has to read
// as something that happened *to* it, not something an unnamed actor did *to* an object.
const KIND_VERBS: Record<string, string> = {
  scrape: "was published",
  people_edit: "was edited",
  sheet_import: "had data imported",
  jurisdiction_edit: "was edited",
  rollback: "had changes rolled back",
};

export function verbFor(kind: string | null): string {
  return (kind && KIND_VERBS[kind]) ?? "was updated";
}

// The DB already collapses same-day/same-town publishes into one row — the actor's own
// name carries the sentence, so this is only the trailing count when there's more than one.
export function reviewCountSuffix(review_count: number): string {
  return review_count > 1 ? `(${review_count} updates)` : "";
}

// Public, unauthenticated feed — jurisdictions that changed, not who changed them. No
// author anywhere in here on purpose (see schemas/activity.py::PublicPublication).
export function renderRecentPublications({
  publications,
}: {
  publications: RecentPublication[];
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
                <a
                  class="recent-publications__jurisdiction"
                  href="/${jurisdictionOcdidToPath(pub.jurisdiction_ocdid)}"
                  >${pub.jurisdiction_name}</a
                >
                <em class="recent-publications__verb">${verbFor(pub.kind)}</em>
                ${reviewCountSuffix(pub.review_count)
                  ? html`<span class="recent-publications__meta"
                      >${reviewCountSuffix(pub.review_count)}</span
                    >`
                  : ""}
                ${pub.commit_url
                  ? html`<a
                      class="recent-publications__meta recent-publications__commit"
                      href=${pub.commit_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      >commit</a
                    >`
                  : ""}
              </span>
              <span class="recent-publications__state">${stateNameForCode(pub.state)}</span>
            </div>
          `,
        )}
      </div>
    </div>
  `;
}
