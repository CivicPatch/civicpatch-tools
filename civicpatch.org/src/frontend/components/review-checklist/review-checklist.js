import "./review-checklist.css";
import { html, component } from "haunted";
import { isChecked } from "../review/issue-checks.ts";

const ORIGIN_SOURCE_LABELS = {
  google_gemini: "Google Gemini",
  existing: "Existing",
};

// The complete index of a card's issues (§8.1) — anchored ones appear here AND
// on the card they anchor to; list-level ones appear only here, because no card
// can act on them.
//
// Ticking stays available on a read-only card: a tick is personal progress in
// this browser, not a mutation of the card, so tracking what you have read
// through is legitimate (§8.3).
function ReviewChecklist({ reviewData, checks = {}, onToggleIssue }) {
  const researchLabel = ORIGIN_SOURCE_LABELS[reviewData?.origin_source] ?? "Research";

  if (!reviewData) return html``;

  const renderCheckmark = (value) =>
    value
      ? html`<i class="fa-solid fa-check" style="color: var(--pico-ins-color);"></i>`
      : html`<i class="fa-solid fa-xmark" style="color: var(--pico-del-color);"></i>`;

  return html`
    <div class="review-checklist">
      ${reviewData.issues?.length ? html`
        <div class="review-checklist__issues">
          <div class="review-checklist__head">
            <h4 class="review-checklist__section-title">Issues</h4>
            <span class="review-checklist__progress">
              ${reviewData.issues.filter((issue) => isChecked(checks, issue)).length}
              of ${reviewData.issues.length} checked
            </span>
          </div>
          <ul class="review-checklist__list">
            ${reviewData.issues.map((issue) => {
              const done = isChecked(checks, issue);
              return html`
                <li class="review-checklist__item ${done ? "review-checklist__item--done" : ""}">
                  <label>
                    <input
                      type="checkbox"
                      .checked=${done}
                      @change=${() => onToggleIssue?.(issue)}
                    />
                    <span>${issue.message}</span>
                  </label>
                </li>
              `;
            })}
          </ul>
          <p class="review-checklist__privacy">Only you can see these ticks.</p>
        </div>
      ` : ""}

      ${reviewData.people_by_source?.length ? html`
        <div class="review-checklist__people">
          <h4 class="review-checklist__section-title">People by Source</h4>
          <table role="grid">
            <thead>
              <tr>
                <th>Name</th>
                <th style="text-align: center;">${researchLabel}</th>
                <th style="text-align: center;">Data</th>
              </tr>
            </thead>
            <tbody>
              ${reviewData.people_by_source.map(row => html`
                <tr>
                  <td>${row.name}</td>
                  <td style="text-align: center;">${renderCheckmark(row.in_research)}</td>
                  <td style="text-align: center;">${renderCheckmark(row.in_data)}</td>
                </tr>
              `)}
            </tbody>
          </table>
        </div>
      ` : ""}
    </div>
  `;
}

customElements.define("civ-review-checklist", component(ReviewChecklist, { useShadowDOM: false }));
