// Preview (spec §7) — the published result, not a diff.
//
// Deliberately carries no diff vocabulary: no state colours, no strikethrough,
// no attention icons. The question it answers is "what will the site say about
// this council", and what the scrape did to get there is not part of that.
//
// Live, because it renders from the same cards Detail edits — including behind
// an open modal.

import { html, nothing } from "lit-html";
import { component } from "haunted";
import "../person-image.js";
import "./review-preview.css";
import { renderPersonRow } from "../people/person-row.js";
import { renderValues, sourceMapFor, type SourceMap } from "./preview-values.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import {
  blockingErrors,
  bySeat,
  publishSet,
  PersonStatus,
  type PersonCard,
} from "../people/person-cards.js";

interface ReviewPreviewProps {
  cards: PersonCard[];
  jurisdictionOcdid: string | null | undefined;
  onOpenPerson: (personId: string, fieldKey: string | null) => void;
}

// Not clickable: this is the published record, so the values are plain selectable
// text you can copy field by field. Nothing here opens an editor.
function renderCard(card: PersonCard, sources: SourceMap) {
  const record = card.newRecord;
  const division = divisionOcdidToFriendly(record?.office?.division_ocdid ?? "") || "";
  const office = [record?.office?.name, division].filter(Boolean).join(", ");

  return renderPersonRow({
    record,
    name: record?.name || "(unnamed)",
    subtitle: office,
    // Status tints the card here too. Preview still carries no other diff
    // vocabulary — no badge, no strikethrough, no attention icon — so the tint is
    // the one cue, and only ever a background.
    modifier: card.status,
    meta: renderValues(record, sources),
  });
}

function ReviewPreview(props: ReviewPreviewProps) {
  const { cards, jurisdictionOcdid } = props;
  const publishing = publishSet(cards ?? []);
  const ordered = bySeat(publishing, jurisdictionOcdid);
  const blockers = blockingErrors(cards ?? []);
  const sources = sourceMapFor(publishing.map((card) => card.newRecord));

  const added = publishing.filter((c) => c.status === PersonStatus.ADDED).length;
  // Everyone with a record who is not being published — the scrape lost them or
  // the reviewer dropped them. Both are "dropped" from the roster's point of view.
  const dropped = (cards ?? []).length - publishing.length;

  return html`
    <div class="review-preview">
      <div class="review-preview__bar">
        <span class="review-preview__count">
          ${ordered.length} official${ordered.length === 1 ? "" : "s"} will be published
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

      ${ordered.length
        ? html`<div class="review-preview__grid">
            ${ordered.map((card) => renderCard(card, sources))}
          </div>`
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
