
import { html, nothing } from "lit-html";
import { component } from "haunted";
import "../person-image.js";
import "./review-preview.css";
import { renderPersonCardGrid } from "../people/person-card-grid.js";
import {
  blockingErrors,
  publishSet,
  PersonStatus,
  type PersonCard,
} from "../people/person-cards.js";
import { type RoleOption } from "../posts-list/posts-model.js";

interface ReviewPreviewProps {
  cards: PersonCard[];
  roles: RoleOption[];
}

function ReviewPreview(props: ReviewPreviewProps) {
  const { cards, roles } = props;
  const publishing = publishSet(cards ?? []);
  const blockers = blockingErrors(cards ?? []);
  const added = publishing.filter((c) => c.status === PersonStatus.ADDED).length;
  const dropped = (cards ?? []).length - publishing.length;
  return html`
    <div class="review-preview">
      <div class="review-preview__bar">
        <span class="review-preview__count">
          ${publishing.length} official${publishing.length === 1 ? "" : "s"} will be published
        </span>
        <span class="review-preview__sub">
          ${added} new, ${dropped} dropped
        </span>
      </div>
      ${blockers.length
        ? html`<div class="review-preview__blockers">
            <span class="review-preview__blockers-title">
              ${blockers.length} thing${blockers.length === 1 ? "" : "s"} to fix before publishing
            </span>
            <ul>
              ${blockers.map(
                (blocker) => html`<li>
                  ${blocker.name} — ${blocker.fieldLabel}: ${blocker.message}
                </li>`,
              )}
            </ul>
          </div>`
        : nothing}
      ${publishing.length
        ? renderPersonCardGrid(publishing, roles)
        : html`<p class="review-preview__empty">
            This card would publish an empty roster.
          </p>`}
    </div>
  `;
}

customElements.define(
  "review-preview",
  component(ReviewPreview as unknown as () => unknown, { useShadowDOM: false }),
);
