// The published roster, drawn with the same cards Overview and Preview draw.
//
// `onOpen` is what makes a card editable: renderPersonRow branches to its
// --static variant when it is absent, so withholding it is how the open-PR guard
// and the read-only case are expressed — not a second kind of card.

import { html, nothing } from "lit-html";
import "../../components/person-image.js";
import "../../components/people/person-row.css";
import { renderPersonRow } from "../../components/people/person-row.js";
import {
  renderValues,
  sourceMapFor,
  type SourceMap,
} from "../../components/review-preview/preview-values.js";
import { divisionOcdidToFriendly } from "../../components/ocdid-utils.js";
import { type PersonCard } from "../../components/people/person-cards.js";

export interface OfficialsCardsProps {
  cards: PersonCard[];
  isLoading: boolean;
  blockedReason: string | null;
  actions?: unknown;
  onOpenPerson: ((personId: string) => void) | null;
}

function renderCard(
  card: PersonCard,
  sources: SourceMap,
  onOpenPerson: ((personId: string) => void) | null,
) {
  const record = card.newRecord;
  const division = divisionOcdidToFriendly(record?.office?.division_ocdid ?? "") || "";
  const office = [record?.office?.name, division].filter(Boolean).join(", ");
  const name = record?.name || "(unnamed)";

  return renderPersonRow({
    record,
    name,
    subtitle: office,
    ariaLabel: `Edit ${name}`,
    modifier: card.status,
    onOpen: onOpenPerson ? () => onOpenPerson(card.personId) : null,
    meta: renderValues(record, sources),
  });
}

export function renderOfficialsCards(props: OfficialsCardsProps) {
  const { cards, isLoading, blockedReason, actions, onOpenPerson } = props;
  const sources = sourceMapFor(cards.map((card) => card.newRecord));

  return html`
    <section class="jurisdiction-section">
      <div class="jurisdiction-section__head">
        <div class="jurisdiction-section__heading">
          <h2 class="jurisdiction-section__title">Officials</h2>
          <span class="jurisdiction-section__meta">
            ${isLoading
              ? "Loading…"
              : `${cards.length} ${cards.length === 1 ? "person" : "people"}`}
          </span>
        </div>
        ${actions
          ? html`<span class="jurisdiction-section__actions">${actions}</span>`
          : nothing}
      </div>

      ${blockedReason
        ? html`<p class="jurisdiction-section__blocked">
            <i class="fa-solid fa-lock" aria-hidden="true"></i> ${blockedReason}
          </p>`
        : nothing}

      ${isLoading
        ? nothing
        : cards.length
          ? html`<div class="review-preview__grid">
              ${cards.map((card) => renderCard(card, sources, onOpenPerson))}
            </div>`
          : html`<p class="jurisdiction-section__meta">
              No officials published for this jurisdiction yet.
            </p>`}
    </section>
  `;
}
