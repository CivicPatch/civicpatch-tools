// The published roster, drawn with the same cards Overview and Preview draw.
//
// `onOpen` is what makes a card editable: renderPersonRow branches to its
// --static variant when it is absent, so withholding it is how the open-PR guard
// and the read-only case are expressed — not a second kind of card.

import { html, nothing } from "lit-html";
import "../../components/person-image.js";
import "../../components/people/person-row.css";
import {
  renderPersonGrid,
  type PersonRowProps,
} from "../../components/people/person-row.js";
import {
  renderValues,
  sourceMapFor,
  type SourceMap,
} from "../../components/review-preview/preview-values.js";
import { type PersonCard } from "../../components/people/person-cards.js";
import { postsHeld } from "../../components/posts-list/posts-model.js";

export interface RosterCardsProps {
  cards: PersonCard[];
  isLoading: boolean;
  blockedReason: string | null;
  actions?: unknown;
  onOpenPerson: ((personId: string) => void) | null;
}

function rowFor(
  card: PersonCard,
  sources: SourceMap,
  onOpenPerson: ((personId: string) => void) | null,
): PersonRowProps {
  const record = card.newRecord;
  // Post label, then membership label. Not `office.name` plus a division badge: that read
  // "Council Member District 5 - Councilmember District 5, [D5]" — two spellings of one office
  // joined by us, then the district a third time.
  const office = postsHeld(record?.memberships ?? []);
  const name = record?.name || "(unnamed)";

  return {
    record,
    name,
    subtitle: office,
    ariaLabel: `Edit ${name}`,
    modifier: card.status,
    onOpen: onOpenPerson ? () => onOpenPerson(card.personId) : null,
    meta: renderValues(record, sources),
  };
}

export function renderRosterCards(props: RosterCardsProps) {
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
          ? renderPersonGrid(
              cards.map((card) => rowFor(card, sources, onOpenPerson)),
            )
          : html`<p class="jurisdiction-section__meta">
              No people published for this jurisdiction yet.
            </p>`}
    </section>
  `;
}
