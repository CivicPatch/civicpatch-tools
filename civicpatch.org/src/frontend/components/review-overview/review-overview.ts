import { html, nothing } from "lit-html";
import { component } from "haunted";
import "../person-image.js";
import "../people/person-card-grid.css";
import "./review-overview.css";
import { type PersonEditorProps } from "../person-editor/person-editor.js";
import { type Post, type RoleOption } from "../posts-list/posts-model.js";
import { renderRoleGroup } from "../people/person-card-grid.js";
import {
  personOf,
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
  foundNobody,
  sectionsByOrganization,
  sourceMapFor,
  tallyOf,
  type CardInOrganization,
  type SourceMap,
} from "./overview-model.js";

export interface ReviewOverviewProps {
  cards: PersonCard[];
  isReadOnly: boolean;
  onOpenPerson: (personId: string, fieldKey: string | null) => void;
  onAdd?: () => void;
  openPersonId: string | null;
  editorFor: (card: PersonCard) => PersonEditorProps;
  posts: Post[];
  roles: RoleOption[];
  assertions: Record<string, PersonAssertion[]>;
  overriddenSourceValues: Record<string, Record<string, unknown>>;
  // Named so a section heading can say whose roster it is. A proposal names its organization by
  // id only, and an id is not a heading.
  organizations?: { id: string; name: string }[];
}

const UNMATCHED_SECTION_LABEL = "Unmatched role";
const DEPARTING_SECTION_LABEL = "Not found or removed";
const UNPLACED_SECTION_LABEL = "No office yet";
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

// No editor slots interleaved here — `renderRoleGroup` (person-card-grid.ts) owns where the
// group breaks for the open card; this only owns how a given subset of cards renders inside
// whichever box it lands in — runs of folded strips and full diff cards, same as always.
function renderCardRuns(
  cards: PersonCard[],
  props: ReviewOverviewProps,
  sources: SourceMap,
) {
  return runsOf(cards).map((run) =>
    run.folded
      ? html`<div class="review-overview__strip">
          ${run.cards.map((card) => renderFold(card, props))}
        </div>`
      : run.cards.map((card) => renderDiffCard(card, props, sources)),
  );
}

function renderSection(
  heading: string,
  entries: CardInOrganization[],
  props: ReviewOverviewProps,
  sources: SourceMap,
) {
  return renderRoleGroup(
    heading,
    entries,
    (entry: CardInOrganization) => entry.card.personId,
    (subset: CardInOrganization[]) =>
      renderCardRuns(subset.map((entry) => entry.card), props, sources),
    props.openPersonId,
    (entry: CardInOrganization) => renderInlineEditor(entry.card, props),
  );
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

/** Somebody a reviewer just added, before they have been given an office. Their own group, at
 * the end: they used to sit with the departing, where "not found" read as a verdict on a person
 * who had just arrived.
 *
 * A plain list of cards, so `renderRoleGroup` serves it — unlike departing, which collapses
 * past the second into chips and needs its own shape. */
function renderUnplacedSection(
  cards: PersonCard[],
  props: ReviewOverviewProps,
  sources: SourceMap,
) {
  return renderRoleGroup(
    UNPLACED_SECTION_LABEL,
    cards,
    (card: PersonCard) => card.personId,
    (subset: PersonCard[]) =>
      subset.map((card) => renderDiffCard(card, props, sources)),
    props.openPersonId,
    (card: PersonCard) => renderInlineEditor(card, props),
  );
}

// Shaped like `renderRoleGroup`'s split, but by hand: departing has its own hybrid layout
// (full cards, then collapsed chips) that doesn't fit the plain "list of cards" shape
// `renderRoleGroup` expects. Only `shown` has real positions worth preserving around the open
// card — a chip in `rest` has no row of its own to protect, so opening one just adds the
// editor after everything instead.
function renderDepartingSection(
  cards: PersonCard[],
  props: ReviewOverviewProps,
  sources: SourceMap,
) {
  if (!cards.length) return nothing;
  const shown = cards.slice(0, DEPARTING_SHOWN);
  const rest = cards.slice(DEPARTING_SHOWN);
  const head = html`<div class="rgrouphead">
    ${DEPARTING_SECTION_LABEL} <span class="sub">${cards.length}</span>
  </div>`;
  const openIndex = props.openPersonId
    ? shown.findIndex((card) => card.personId === props.openPersonId)
    : -1;

  if (openIndex === -1) {
    const openInRest = cards.find(
      (card) => card.personId === props.openPersonId && rest.includes(card),
    );
    return html`
      <div class="rgroup" style="--group-cards: ${shown.length}">
        ${head}
        <div class="rgrid">
          ${shown.map((card) => renderDiffCard(card, props, sources))}
        </div>
        ${rest.length ? renderDepartingChips(rest, props) : nothing}
      </div>
      ${openInRest ? renderInlineEditor(openInRest, props) : nothing}
    `;
  }

  const upToOpen = shown.slice(0, openIndex + 1);
  const after = shown.slice(openIndex + 1);
  return html`
    <div class="rgroup" style="--group-cards: ${shown.length}">
      ${head}
      <div class="rgrid">
        ${upToOpen.map((card) => renderDiffCard(card, props, sources))}
      </div>
    </div>
    ${renderInlineEditor(shown[openIndex], props)}
    ${after.length || rest.length
      ? html`
          <div class="rgroup" style="--group-cards: ${shown.length}">
            <div class="rgrid">
              ${after.map((card) => renderDiffCard(card, props, sources))}
            </div>
            ${rest.length ? renderDepartingChips(rest, props) : nothing}
          </div>
        `
      : nothing}
  `;
}

/** One organization's roster, headed the way the jurisdiction page heads its own (`.panel`,
 * `panel__cap`), with the roles inside it. */
function renderOrganization(
  organizationId: string,
  entries: CardInOrganization[],
  ranked: { roleLabel: string; people: CardInOrganization[] }[],
  unmatched: CardInOrganization[],
  props: ReviewOverviewProps,
  sources: SourceMap,
) {
  const name =
    props.organizations?.find((organization) => organization.id === organizationId)?.name ??
    "This jurisdiction";
  const people = new Set(entries.map((entry) => entry.card.personId)).size;
  return html`
    <section class="panel review-overview__organization">
      <div class="panel__cap">
        <b>${name}</b>
        <span class="jurisdiction-section__meta">
          ${foundNobody(entries)
            ? "not found in this scrape, nothing here changes"
            : `${people} ${people === 1 ? "person" : "people"}`}
        </span>
      </div>
      <div class="rgroup-list">
        ${ranked.map((group) =>
          renderSection(group.roleLabel, group.people, props, sources),
        )}
        ${renderSection(UNMATCHED_SECTION_LABEL, unmatched, props, sources)}
      </div>
    </section>
  `;
}

function ReviewOverview(props: ReviewOverviewProps) {
  const { cards, isReadOnly, onAdd, roles } = props;
  const list = cards ?? [];
  const sources = sourceMapFor(list);
  const roleOrder = roles.map((role) => role.id);
  const sections = sectionsByOrganization(
    list,
    roleOrder,
    (props.organizations ?? []).map((organization) => organization.id),
  );

  return html`
    <div class="review-overview">
      ${renderTally(list)}
      ${list.length
        ? html`<div class="rgroup-list">
            ${sections.organizations.map((organization) =>
              renderOrganization(
                organization.organizationId,
                [...organization.ranked.flatMap((group) => group.people), ...organization.unmatched],
                organization.ranked,
                organization.unmatched,
                props,
                sources,
              ),
            )}
            ${renderDepartingSection(sections.departing, props, sources)}
            ${renderUnplacedSection(sections.unplaced, props, sources)}
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
