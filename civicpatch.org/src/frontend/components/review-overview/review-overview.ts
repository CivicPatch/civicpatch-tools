import { html, nothing } from "lit-html";
import { component } from "haunted";
import "../person-image.js";
import "../people/person-card-grid.css";
import "./review-overview.css";
import { type PersonEditorProps } from "../person-editor/person-editor.js";
import { type Post, type RoleOption } from "../posts-list/posts-model.js";
import {
  proposalsByPersonId,
  personOf,
  type ProposedChange,
  type PersonCard,
} from "../people/person-cards.js";
import { type PersonAssertion } from "../person-editor/field-provenance.js";
import {
  rowLabel,
  renderDiffCard,
  renderFold,
  renderInlineEditor,
} from "./diff-card.js";
import {
  runsOf,
  sectionsOf,
  sourceMapFor,
  tallyOf,
  type SourceMap,
} from "./overview-model.js";

export interface ReviewOverviewProps {
  cards: PersonCard[];
  changes?: ProposedChange[];
  isReadOnly: boolean;
  onOpenPerson: (personId: string, fieldKey: string | null) => void;
  onAdd?: () => void;
  openPersonId: string | null;
  editorFor: (card: PersonCard) => PersonEditorProps;
  posts: Post[];
  roles: RoleOption[];
  assertions: Record<string, PersonAssertion[]>;
  overriddenSourceValues: Record<string, Record<string, unknown>>;
}

const UNMATCHED_SECTION_LABEL = "Unmatched role";
const DEPARTING_SECTION_LABEL = "Not found or removed";
// How many departing cards show in full before the rest collapse to name chips — the same
// "less detail up front, not click-through-first" idea `runsOf`'s fold already uses for a
// long run of unchanged people, applied to a long run of dropped ones instead.
const DEPARTING_SHOWN = 2;

function renderTally(cards: PersonCard[]) {
  const tally = tallyOf(cards);
  if (!tally.length) return nothing;
  return html`
    <div class="review-overview__tally">
      ${tally.map(
        (entry) => html`<span
          class="review-row__badge review-row__badge--${entry.status}"
          >${entry.count} ${entry.label}</span
        >`,
      )}
    </div>
  `;
}

// The editor for a card that isn't open renders nothing (renderInlineEditor gates on
// openPersonId), so interleaving one after every card costs nothing except for the one
// that's actually open — which then lands as the very next grid item after its own card,
// `grid-column: 1/-1` breaking the row right there instead of at the bottom of the group.
function renderCardRuns(
  cards: PersonCard[],
  props: ReviewOverviewProps,
  sources: SourceMap,
  proposals: Map<string, ProposedChange[]>,
) {
  return runsOf(cards).map((run) =>
    run.folded
      ? html`<div class="review-overview__strip">
            ${run.cards.map((card) => renderFold(card, props, proposals))}
          </div>
          ${run.cards.map((card) => renderInlineEditor(card, props))}`
      : run.cards.flatMap((card) => [
          renderDiffCard(card, props, sources, proposals),
          renderInlineEditor(card, props),
        ]),
  );
}

function renderSection(
  heading: string,
  cards: PersonCard[],
  props: ReviewOverviewProps,
  sources: SourceMap,
  proposals: Map<string, ProposedChange[]>,
) {
  if (!cards.length) return nothing;
  return html`
    <div class="rgroup" style="--group-cards: ${cards.length}">
      <div class="rgrouphead">
        ${heading} <span class="sub">${cards.length}</span>
      </div>
      <div class="rgrid">${renderCardRuns(cards, props, sources, proposals)}</div>
    </div>
  `;
}

// A long "dropped" list shows the same way a long unchanged run does elsewhere — a couple in
// full, the rest collapsed — except to name chips rather than a fold strip, since a departing
// person has no fields left worth previewing at a glance the way an unchanged one's post does.
function renderDepartingChips(cards: PersonCard[], props: ReviewOverviewProps) {
  return html`<p class="review-overview__more">
    +${cards.length} more removed —
    ${cards.map(
      (card, i) => html`${i > 0 ? ", " : ""}<button
        class="review-overview__chip"
        aria-label=${rowLabel(card)}
        @click=${() => props.onOpenPerson(card.personId, null)}
        >${personOf(card)?.name || "(unnamed)"}</button
      >`,
    )}
  </p>`;
}

function renderDepartingSection(
  cards: PersonCard[],
  props: ReviewOverviewProps,
  sources: SourceMap,
  proposals: Map<string, ProposedChange[]>,
) {
  if (!cards.length) return nothing;
  const shown = cards.slice(0, DEPARTING_SHOWN);
  const rest = cards.slice(DEPARTING_SHOWN);
  return html`
    <div class="rgroup" style="--group-cards: ${shown.length}">
      <div class="rgrouphead">
        ${DEPARTING_SECTION_LABEL} <span class="sub">${cards.length}</span>
      </div>
      <div class="rgrid">
        ${shown.flatMap((card) => [
          renderDiffCard(card, props, sources, proposals),
          renderInlineEditor(card, props),
        ])}
      </div>
      ${rest.length ? renderDepartingChips(rest, props) : nothing}
      ${rest.map((card) => renderInlineEditor(card, props))}
    </div>
  `;
}

function ReviewOverview(props: ReviewOverviewProps) {
  const { cards, isReadOnly, onAdd, roles } = props;
  const proposals = proposalsByPersonId(props.changes ?? []);
  const list = cards ?? [];
  const sources = sourceMapFor(list);
  const roleOrder = roles.map((role) => role.id);
  const sections = sectionsOf(list, proposals, roleOrder);

  return html`
    <div class="review-overview">
      ${renderTally(list)}
      ${list.length
        ? html`<div class="rgroup-list">
            ${sections.ranked.map((group) =>
              renderSection(group.roleLabel, group.people, props, sources, proposals),
            )}
            ${renderSection(UNMATCHED_SECTION_LABEL, sections.unmatched, props, sources, proposals)}
            ${renderDepartingSection(sections.departing, props, sources, proposals)}
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
