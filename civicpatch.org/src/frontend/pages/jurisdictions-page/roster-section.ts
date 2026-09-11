// The published roster, drawn with the same cards Overview and Preview draw.
//
// `onOpen` is what makes a card editable: renderPersonRow branches to its
// --static variant when it is absent, so withholding it is how the open-PR guard
// and the read-only case are expressed — not a second kind of card.

import { html, nothing } from "lit-html";
import "../../components/panel/panel.css";
import "../../components/person-image.js";
import "../../components/people/person-row.css";
import {
  renderPersonGrid,
  renderPersonRow,
  type PersonRowProps,
} from "../../components/people/person-row.js";
import { renderInlinePersonEditor } from "../../components/person-editor/inline-editor.js";
import { type PersonEditorProps } from "../../components/person-editor/person-editor.js";
import {
  renderValues,
  sourceMapFor,
  type SourceMap,
} from "../../components/review-preview/preview-values.js";
import { type PersonCard } from "../../components/people/person-cards.js";
import { postsHeld } from "../../components/posts-list/posts-model.js";

const ROSTER_PERSON_ID_PREFIX = "roster-person-";

export interface RosterCardsProps {
  cards: PersonCard[];
  isLoading: boolean;
  blockedReason: string | null;
  actions?: unknown;
  onOpenPerson: ((personId: string, fieldKey: string | null) => void) | null;
  openPersonId: string | null;
  editorFor: ((card: PersonCard) => PersonEditorProps) | null;
}

function rowFor(
  card: PersonCard,
  sources: SourceMap,
  onOpenPerson: ((personId: string, fieldKey: string | null) => void) | null,
  openPersonId: string | null,
): PersonRowProps {
  const record = card.newRecord;
  // Post label, then membership label. Not `office.name` plus a division badge: that read
  // "Council Member District 5 - Councilmember District 5, [D5]" — two spellings of one office
  // joined by us, then the district a third time.
  const office = postsHeld(record?.memberships ?? []);
  const name = record?.name || "(unnamed)";
  const firstField = card.surviving[0]?.field.key ?? null;

  return {
    record,
    name,
    subtitle: office,
    ariaLabel: `Edit ${name}`,
    modifier: card.status,
    onOpen: onOpenPerson ? () => onOpenPerson(card.personId, firstField) : null,
    isOpen: card.personId === openPersonId,
    controlsId: `${ROSTER_PERSON_ID_PREFIX}${card.personId}`,
    meta: renderValues(record, sources),
  };
}

export function renderRosterCards(props: RosterCardsProps) {
  const { cards, isLoading, blockedReason, actions, onOpenPerson, openPersonId, editorFor } =
    props;
  const sources = sourceMapFor(cards.map((card) => card.newRecord));

  return html`
    <section class="panel">
      <div class="panel__cap">
        <b>Officials</b>
        <span class="jurisdiction-section__meta">
          ${isLoading
            ? "Loading…"
            : `${cards.length} ${cards.length === 1 ? "person" : "people"}`}
        </span>
        ${actions
          ? html`<span class="jurisdiction-section__actions panel__cap-right"
              >${actions}</span
            >`
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
          ? editorFor
            ? html`<div class="review-preview__grid">
                ${cards.flatMap((card) => [
                  renderPersonRow(rowFor(card, sources, onOpenPerson, openPersonId)),
                  renderInlinePersonEditor({
                    card,
                    openPersonId,
                    editorFor,
                    idPrefix: ROSTER_PERSON_ID_PREFIX,
                  }),
                ])}
              </div>`
            : renderPersonGrid(
                cards.map((card) => rowFor(card, sources, onOpenPerson, openPersonId)),
              )
          : html`<p class="jurisdiction-section__meta">
              No people published for this jurisdiction yet.
            </p>`}
    </section>
  `;
}
