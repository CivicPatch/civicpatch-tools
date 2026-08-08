// Overview — triage a whole card at a glance (2026-07-30 spec).
//
// One list in seat order, not two groups: status is carried by the card itself, so
// position is free for the roster order a reviewer checks against a source page.
// People the scrape left untouched fold to a compact row rather than spending a card.

import { html, nothing } from "lit-html";
import { component } from "haunted";
import "../person-image.js";
import "./review-overview.css";
import { renderPersonRow } from "../people/person-row.js";
import { ensureUrl, withDisplayImage } from "../fields/field-controls.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { SOURCE_LINK_TARGET } from "../../utils/source-links.js";
import {
  cardSubtitle,
  DEPARTING,
  personOf,
  PersonStatus,
  STATUS_LABEL,
  type PersonCard,
} from "../people/person-cards.js";
import { type SurvivingField } from "../fields/field-model.js";
import {
  ATTENTION_COPY,
  attentionOf,
  fieldClass,
  FIELD_CAP,
  runsOf,
  sourceMapFor,
  STATUS_BADGE,
  visibleFields,
  type SourceMap,
} from "./overview-model.js";

interface ReviewOverviewProps {
  cards: PersonCard[];
  isReadOnly: boolean;
  onOpenPerson: (personId: string, fieldKey: string | null) => void;
  onAdd?: () => void;
}

// Everything the row says, in one string: the identity area is a single button and
// a screen reader gets its label rather than its parts.
function rowLabel(card: PersonCard): string {
  const parts = [
    personOf(card)?.name || "unnamed",
    STATUS_LABEL[card.status] ?? card.status,
  ];
  if (card.issues.length) {
    parts.push(`${card.issues.length} issue${card.issues.length === 1 ? "" : "s"}`);
  }
  return parts.join(", ");
}

// Real links, and the only thing on the card that is: checking a source without
// opening the person is the point of putting them here. They sit above the card's
// hit area, so the card does not open beneath them — which is why the raised area
// is exactly the tags and nothing around them.
function renderSources(card: PersonCard, sources: SourceMap) {
  const urls = (card.newRecord?.source_urls ?? []).filter(Boolean);
  return urls.map((url: string) => {
    const entry = sources.get(url);
    if (!entry) return nothing;
    return html`<a
      class="review-row__source ${entry.colorClass}"
      href=${ensureUrl(url)}
      target=${SOURCE_LINK_TARGET}
      title=${url}
      >[${entry.number}]</a
    >`;
  });
}

function renderAttention(card: PersonCard) {
  const attention = attentionOf(card);
  if (!attention) return nothing;
  const { icon, label } = ATTENTION_COPY[attention];
  return html`<span class="review-row__attn review-row__attn--${attention}">
    <i class="fa-solid fa-${icon}" aria-hidden="true"></i> ${label}
  </span>`;
}

function renderFields(card: PersonCard, props: ReviewOverviewProps) {
  // A departing person shows no field list: with no new-side record every field
  // reads cleared, so the list would imply nine things to review on one decision.
  if (DEPARTING.has(card.status)) return nothing;
  // Context fields are dropped: source urls render as numbered links instead, so a
  // tag would say the same thing twice.
  const ranked = visibleFields(card);
  const shown = ranked.slice(0, FIELD_CAP);
  const hidden = ranked.length - shown.length;
  // Plain text, not buttons: anything interactive here sits above the card's hit
  // area and punches holes in it. The card opens the person; the tags say why.
  return shown.map(
    (field) => html`<span
      class="review-row__field review-row__field--${fieldClass(field)}"
      >${field.field.label}</span
    >`,
  ).concat(
    hidden > 0
      ? [html`<span class="review-row__more">+${hidden} more</span>`]
      : [],
  );
}

function renderRow(
  card: PersonCard,
  props: ReviewOverviewProps,
  sources: SourceMap,
) {
  const badge = STATUS_BADGE[card.status];
  // The field the card leads with — not surviving[0], which is schema order and
  // would focus a different field from the one the reviewer clicked.
  const firstField = visibleFields(card)[0]?.field.key ?? null;
  return renderPersonRow({
    record: personOf(card),
    name: personOf(card)?.name || "(unnamed)",
    subtitle: cardSubtitle(card, divisionOcdidToFriendly) || "",
    ariaLabel: rowLabel(card),
    onOpen: () => props.onOpenPerson(card.personId, firstField),
    modifier: card.status,
    meta: html`
      ${renderAttention(card)}
      ${badge
        ? html`<span class="review-row__badge review-row__badge--${card.status}"
            >${badge}</span
          >`
        : nothing}
      ${renderFields(card, props)}
      <span class="review-row__sources">${renderSources(card, sources)}</span>
    `,
  });
}

function renderFold(card: PersonCard, props: ReviewOverviewProps) {
  const record = personOf(card);
  return html`
    <span class="review-fold">
      <button
        class="review-fold__open"
        aria-label=${rowLabel(card)}
        @click=${() => props.onOpenPerson(card.personId, null)}
      >
        <person-image
          .person=${withDisplayImage(record)}
          .size=${"2.1rem"}
        ></person-image>
        <span class="review-fold__who">
          <span class="review-fold__name">${record?.name || "(unnamed)"}</span>
          <span class="review-fold__meta">
            <span class="review-fold__sub"
              >${cardSubtitle(card, divisionOcdidToFriendly) || nothing}</span
            >
            ${renderAttention(card)}
          </span>
        </span>
      </button>
      <i class="fa-solid fa-pen-to-square review-row__hint" aria-hidden="true"></i>
    </span>
  `;
}

function ReviewOverview(props: ReviewOverviewProps) {
  const { cards, isReadOnly, onAdd } = props;
  const list = cards ?? [];
  const sources = sourceMapFor(list);

  return html`
    <div class="review-overview">
      ${list.length
        ? html`<div class="review-overview__list">
            ${runsOf(list).map((run) =>
              run.folded
                ? html`<div class="review-overview__strip">
                    ${run.cards.map((card) => renderFold(card, props))}
                  </div>`
                : run.cards.map((card) => renderRow(card, props, sources)),
            )}
            <!-- The ghost is always last: adding someone puts their card where it
                 stood and pushes it down, so the affordance never moves. -->
            ${!isReadOnly && onAdd
              ? html`<button class="review-row review-row--ghost" @click=${onAdd}>
                  <span aria-hidden="true">+</span>
                  <span>Add a person</span>
                </button>`
              : nothing}
          </div>`
        : html`<p class="review-overview__empty">
            This card has no officials.
          </p>`}
    </div>
  `;
}

customElements.define(
  "review-overview",
  component(ReviewOverview as unknown as () => unknown, {
    useShadowDOM: false,
  }),
);
