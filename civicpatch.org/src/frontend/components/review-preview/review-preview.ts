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
import { FIELD_SCHEMA, diffValue, type FieldSpec } from "../review/field-model.js";
import { withDisplayImage } from "../review/field-controls.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import {
  blockingErrors,
  bySeat,
  publishSet,
  RailStatus,
  type ReviewCard,
} from "../review/review-cards.js";

interface ReviewPreviewProps {
  cards: ReviewCard[];
  jurisdictionOcdid: string | null | undefined;
  onOpenPerson: (personId: string, fieldKey: string | null) => void;
}

// Identity is already in the card head, so the field list is what remains.
//
// Sources ARE included, unlike the rest of the review apparatus. §11.2 originally
// excluded them as provenance rather than published data, but that put Preview at
// odds with the collapse rule, which shows source urls always precisely because
// they are the evidence behind every other value. Being able to check where a
// number came from is not review-time overhead; it is part of reading the record.
const DETAIL_FIELDS = FIELD_SCHEMA.filter(
  (field) =>
    !["image", "name", "office.name", "office.division_ocdid"].includes(field.key),
);

function values(card: ReviewCard, field: FieldSpec): string[] {
  const value = diffValue(card.newRecord, field);
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  const text = String(value ?? "").trim();
  return text ? [text] : [];
}

function renderCard(card: ReviewCard, props: ReviewPreviewProps) {
  const record = card.newRecord;
  const division = divisionOcdidToFriendly(record?.office?.division_ocdid ?? "") || "";
  const populated = DETAIL_FIELDS.map((field) => [field, values(card, field)] as const).filter(
    ([, list]) => list.length > 0,
  );

  return html`
    <button
      class="btn-ghost review-preview__card"
      @click=${() => props.onOpenPerson(card.personId, null)}
    >
      <span class="review-preview__head">
        <person-image .person=${withDisplayImage(record)} .size=${"2.75rem"}></person-image>
        <span class="review-preview__who">
          <span class="review-preview__name">${record?.name || "(unnamed)"}</span>
          <span class="review-preview__office">${record?.office?.name || nothing}</span>
          <span class="review-preview__division">${division || nothing}</span>
        </span>
      </span>
      ${populated.length
        ? html`<dl class="review-preview__fields">
            ${populated.map(
              ([field, list]) => html`
                <dt>${field.label}</dt>
                <dd>${list.map((value) => html`<span>${value}</span>`)}</dd>
              `,
            )}
          </dl>`
        : nothing}
    </button>
  `;
}

function ReviewPreview(props: ReviewPreviewProps) {
  const { cards, jurisdictionOcdid } = props;
  const publishing = publishSet(cards ?? []);
  const ordered = bySeat(publishing, jurisdictionOcdid);
  const blockers = blockingErrors(cards ?? []);

  const added = publishing.filter((c) => c.status === RailStatus.ADDED).length;
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
          ${added} new · ${dropped} dropped
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
            ${ordered.map((card) => renderCard(card, props))}
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
