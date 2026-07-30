// Overview — triage a whole card at a glance (spec §4).
//
// A photo grid, split into what needs review and the roster that doesn't. No
// filter chips: the two groups replace them, and §3's predicate decides
// membership from the same collapse computation the rail uses, so the two views
// can never disagree about who needs attention.

import { html, nothing } from "lit-html";
import { component } from "haunted";
import "../person-image.js";
import "./review-overview.css";
import { withDisplayImage } from "../review/field-controls.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import {
  DEPARTING,
  groupCards,
  personOf,
  RailStatus,
  STATUS_LABEL,
  type ReviewCard,
} from "../review/review-cards.js";

interface ReviewOverviewProps {
  cards: ReviewCard[];
  isReadOnly: boolean;
  // Opening the editor. Until the modal lands (§17 step 6) the page answers
  // these by switching to Detail — a tile always leads somewhere.
  onOpenPerson: (personId: string, fieldKey: string | null) => void;
  onAdd?: () => void;
}

function subtitle(card: ReviewCard): string {
  const record = personOf(card);
  const office = record?.office?.name ?? "";
  const division = divisionOcdidToFriendly(record?.office?.division_ocdid ?? "") || "";
  return [office, division].filter(Boolean).join(" · ");
}

// Everything the tile says, in one string, because the tile is a single button
// and a screen reader gets its label rather than its parts.
function tileLabel(card: ReviewCard): string {
  const record = personOf(card);
  const parts = [record?.name || "unnamed", STATUS_LABEL[card.status] ?? card.status];
  if (card.issues.length) parts.push(`${card.issues.length} issue${card.issues.length === 1 ? "" : "s"}`);
  else if (card.surviving.length) parts.push(`${card.surviving.length} field${card.surviving.length === 1 ? "" : "s"} to review`);
  return parts.join(", ");
}

function renderTile(card: ReviewCard, props: ReviewOverviewProps) {
  const record = personOf(card);
  const departing = DEPARTING.has(card.status);
  // A departing person shows no field list. With no new-side record every field
  // reads `cleared`, so the list would imply nine things to review on a card that
  // is one decision.
  //
  // There is no count badge: the footer names the surviving fields, which is
  // strictly more information than a number counting them.
  return html`
    <div class="review-tile review-tile--${card.status}">
      <button
        class="review-tile__open"
        aria-label=${tileLabel(card)}
        @click=${() =>
          props.onOpenPerson(card.personId, card.surviving[0]?.field.key ?? null)}
      >
        <span class="review-tile__photo">
          <person-image
            .person=${withDisplayImage(record)}
            .size=${"6rem"}
          ></person-image>
          <span class="review-tile__over">
            <span class="review-tile__name">${record?.name || "(unnamed)"}</span>
            <span class="review-tile__office">${subtitle(card) || nothing}</span>
          </span>
        </span>
      </button>
      <!-- Departing people show no field list: the card is one decision. -->
      ${departing
        ? nothing
        : html`<span class="review-tile__foot">
            ${card.surviving.map(
              (field) => html`<button
                class="review-tile__field review-tile__field--${field.error
                  ? "error"
                  : field.reason === "issue"
                    ? "issue"
                    : field.state}"
                @click=${() => props.onOpenPerson(card.personId, field.field.key)}
              >
                ${field.field.label}
              </button>`,
            )}
          </span>`}
    </div>
  `;
}

function renderFace(card: ReviewCard, props: ReviewOverviewProps) {
  const record = personOf(card);
  return html`<button
    class="review-face"
    @click=${() => props.onOpenPerson(card.personId, null)}
  >
    <person-image
      .person=${withDisplayImage(record)}
      .size=${"1.75rem"}
    ></person-image>
    <span>${record?.name || "(unnamed)"}</span>
  </button>`;
}

function ReviewOverview(props: ReviewOverviewProps) {
  const { cards, isReadOnly, onAdd } = props;
  const { toReview, unchanged } = groupCards(cards ?? []);

  return html`
    <div class="review-overview">
      <section class="review-overview__group">
        <header class="review-overview__head">
          <span class="review-overview__title">To review</span>
          <span class="review-overview__count">${toReview.length}</span>
        </header>
        ${toReview.length || (!isReadOnly && onAdd)
          ? html`<div class="review-overview__grid">
              ${toReview.map((card) => renderTile(card, props))}
              ${!isReadOnly && onAdd
                ? html`<button class="review-tile review-tile--ghost" @click=${onAdd}>
                    <span aria-hidden="true">+</span>
                    <span>Add a person the scrape missed</span>
                  </button>`
                : nothing}
            </div>`
          : html`<p class="review-overview__empty">Nothing needs review on this card.</p>`}
      </section>

      ${unchanged.length
        ? html`<section class="review-overview__group">
            <header class="review-overview__head">
              <span class="review-overview__title">Unchanged</span>
              <span class="review-overview__count">${unchanged.length}</span>
            </header>
            <!-- A face strip, not tiles — the roster reads complete without
                 spending a card on people with nothing to say. -->
            <div class="review-overview__faces">
              ${unchanged.map((card) => renderFace(card, props))}
            </div>
          </section>`
        : nothing}
    </div>
  `;
}

customElements.define(
  "review-overview",
  component(ReviewOverview as unknown as () => unknown, { useShadowDOM: false }),
);
