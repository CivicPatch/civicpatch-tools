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

// The DB already collapses same-day/same-town publishes into one row (review_count says
// how many) — this is just the label, so a heavily-reviewed town reads as one line, not
// as several near-identical rows crowding out everyone else.
export function reviewLabel({
  author_name,
  review_count,
}: Pick<RecentPublication, "author_name" | "review_count">) {
  return review_count > 1
    ? `reviewed ${review_count} times, most recently by ${author_name}`
    : `reviewed by ${author_name}`;
}

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
              <a
                class="recent-publications__name"
                href="/${jurisdictionOcdidToPath(pub.jurisdiction_ocdid)}"
                >${pub.jurisdiction_name}</a
              >
              <span class="recent-publications__state"
                >${stateNameForCode(pub.state ?? "")}</span
              >
              <span class="recent-publications__meta">
                ${reviewLabel(pub)}, ${formatDate(pub.created_at)}
                ${pub.commit_url
                  ? html`<a
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
