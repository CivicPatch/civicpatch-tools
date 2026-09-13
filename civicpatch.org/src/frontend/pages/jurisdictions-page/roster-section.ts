// The published roster, drawn with the same grouped card grid either way — the .rgroup/
// .rperson pattern (bucket-1 option 1b of the officials-card audit). `onOpenPerson` is what
// makes a card open into the inline editor; withholding it is how the open-PR guard and the
// read-only case are expressed, not a second kind of card.

import { html, nothing } from "lit-html";
import "../../components/panel/panel.css";
import "../../components/person-image.js";
import {
  renderPersonCardGrid,
} from "../../components/people/person-card-grid.js";
import { renderInlinePersonEditor } from "../../components/person-editor/inline-editor.js";
import { type PersonEditorProps } from "../../components/person-editor/person-editor.js";
import { type PersonCard } from "../../components/people/person-cards.js";
import { type RoleOption } from "../../components/posts-list/posts-model.js";

const ROSTER_PERSON_ID_PREFIX = "roster-person-";

export interface RosterCardsProps {
  cards: PersonCard[];
  isLoading: boolean;
  blockedReason: string | null;
  actions?: unknown;
  onOpenPerson: ((personId: string, fieldKey: string | null) => void) | null;
  openPersonId: string | null;
  editorFor: ((card: PersonCard) => PersonEditorProps) | null;
  // Global role vocabulary, in canonical priority order — the card grid uses it to group
  // people under their best-ranked role.
  roles: RoleOption[];
}

export function renderRosterCards(props: RosterCardsProps) {
  const { cards, isLoading, blockedReason, actions, onOpenPerson, openPersonId, editorFor, roles } =
    props;

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
          ? renderPersonCardGrid(cards, roles, {
              onOpenPerson: onOpenPerson
                ? (card) => onOpenPerson(card.personId, card.surviving[0]?.field.key ?? null)
                : null,
              openPersonId,
              renderEditor: editorFor
                ? (card) =>
                    renderInlinePersonEditor({
                      card,
                      openPersonId,
                      editorFor,
                      idPrefix: ROSTER_PERSON_ID_PREFIX,
                    })
                : null,
            })
          : html`<p class="jurisdiction-section__meta">
              No people published for this jurisdiction yet.
            </p>`}
    </section>
  `;
}
