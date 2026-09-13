// Bucket 1 of the officials-card audit (.scratch/wire-demo/person-cards-demo.html) — option
// 1b, the grouped card grid. Same classes as the earlier jurisdiction-page mock
// (.scratch/wire-demo/js/jurisdiction.js + css/app.css): .rgroup/.rgrouphead/.rgrid/.rperson
// for the group shell, .pc-av/.pc-ident/.pc-name/.pc-vals/.pv/.pvk for the person itself —
// reused verbatim rather than re-namespaced, per that file's own "already sketched" note.
// Shared by both the read-only jurisdiction view and the editable roster — a card opens into
// the inline editor when `onOpenPerson` is given, stays flat otherwise. Same markup either
// way, matching Bucket 2's "one card, two contexts" idiom.
//
// person-image.js stands in for the mock's raw <img class="pc-av">/<span class="pc-av"> —
// same slot, same class, but delegating to the one avatar component every other card in the
// app already uses (initials fallback, broken-image handling) rather than duplicating that
// logic here.
//
// Field rows use their own text-label renderer rather than review-preview's icon-based
// renderValues(), matching the mock's plain "term ends …" / "email …" style. The underlying
// field data logic (DETAIL_FIELDS, values(), renderLink(), renderSources()) is still the real,
// shared one — only the label-vs-icon presentation differs.

import { html, nothing } from "lit-html";
import "../person-image.js";
import "./person-card-grid.css";
import { type PersonCard, personOf } from "./person-cards.js";
import { type RoleOption } from "../posts-list/posts-model.js";
import { type DiffRecord, type FieldSpec } from "../fields/field-model.js";
import { PERSON_LINK_TARGET } from "../../utils/source-links.js";
import {
  DETAIL_FIELDS,
  SOURCES_KEY,
  values,
  renderLink,
  renderSources,
  sourceMapFor,
  type SourceMap,
} from "../review-preview/preview-values.js";
import { groupByRole, type RoleGroup } from "./person-card-grid-model.js";

const AVATAR_SIZE = "4rem";

export interface PersonCardGridOptions {
  onOpenPerson?: ((card: PersonCard) => void) | null;
  openPersonId?: string | null;
  renderEditor?: ((card: PersonCard) => unknown) | null;
}

function renderFieldValue(field: FieldSpec, list: string[]) {
  if (field.key === "urls")
    return list.map((url) => renderLink(url, url, PERSON_LINK_TARGET, "pc-url"));
  if (field.key === "emails")
    return list.map((email, i) => html`${i > 0 ? ", " : ""}<a class="review-preview__link" href="mailto:${email}">${email}</a>`);
  if (field.key === "phones")
    return list.map((phone, i) => html`${i > 0 ? ", " : ""}<a class="review-preview__link" href="tel:${phone}">${phone}</a>`);
  return list.join(", ");
}

function renderFieldRow(field: FieldSpec, list: string[]) {
  return html`<span class="pv">
    <span class="pvk">${field.label.toLowerCase()}</span>
    <span class="pvv">${renderFieldValue(field, list)}</span>
  </span>`;
}

function renderFields(record: DiffRecord, sources: SourceMap) {
  const populated = DETAIL_FIELDS.filter((field) => field.key !== SOURCES_KEY)
    .map((field) => [field, values(record, field)] as const)
    .filter(([, list]) => list.length > 0);
  return html`<span class="pc-vals">
    ${populated.map(([field, list]) => renderFieldRow(field, list))}
    ${renderSources(record, sources)}
  </span>`;
}

// The group heading already says the role — a membership's own `label` is whatever the
// source said beyond it (a district, a seat), so that's the only thing worth repeating here.
function subtitleFor(record: DiffRecord): string {
  return (record?.memberships as { label: string | null }[] | undefined)?.[0]?.label ?? "";
}

// Only a real <a> (an email, phone, url or source link inside the card) should keep its own
// click — everything else on the card, avatar and field text included, opens the editor.
const isLinkClick = (e: Event) => !!(e.target as HTMLElement).closest("a");

function renderPerson(
  card: PersonCard,
  sources: SourceMap,
  { onOpenPerson, openPersonId }: PersonCardGridOptions,
) {
  const record = personOf(card);
  const name = record?.name || "(unnamed)";
  const subtitle = subtitleFor(record);
  const isOpen = onOpenPerson ? card.personId === openPersonId : false;
  const nameBlock = html`<span class="pc-name">${name}</span>
    ${subtitle ? html`<span class="pc-sub">${subtitle}</span>` : nothing}`;
  const openThisPerson = () => onOpenPerson?.(card);
  const handleClick = (e: MouseEvent) => {
    if (!isLinkClick(e)) openThisPerson();
  };
  const handleKeydown = (e: KeyboardEvent) => {
    if ((e.key === "Enter" || e.key === " ") && !isLinkClick(e)) {
      e.preventDefault();
      openThisPerson();
    }
  };
  return html`
    <div
      class="rperson ${onOpenPerson ? "rperson--interactive" : ""} ${isOpen ? "rperson--open" : ""}"
      role=${onOpenPerson ? "button" : nothing}
      tabindex=${onOpenPerson ? "0" : nothing}
      aria-expanded=${onOpenPerson ? isOpen : nothing}
      @click=${onOpenPerson ? handleClick : nothing}
      @keydown=${onOpenPerson ? handleKeydown : nothing}
    >
      <span class="pc-av">
        <person-image .person=${record ?? {}} .size=${AVATAR_SIZE}></person-image>
      </span>
      <span class="pc-ident">
        <span class="pc-open">${nameBlock}</span>
        ${renderFields(record, sources)}
      </span>
      ${onOpenPerson
        ? html`<i class="fa-solid fa-chevron-down pc-hint" aria-hidden="true"></i>`
        : nothing}
    </div>
  `;
}

function renderGroup(
  group: RoleGroup<{ card: PersonCard }>,
  sources: SourceMap,
  options: PersonCardGridOptions,
) {
  const { renderEditor } = options;
  return html`
    <div class="rgroup">
      <div class="rgrouphead">
        ${group.roleLabel}${group.people.length > 1
          ? html` <span class="sub">${group.people.length}</span>`
          : nothing}
      </div>
      <div class="rgrid">
        ${group.people.flatMap(({ card }) => [
          renderPerson(card, sources, options),
          renderEditor ? renderEditor(card) : nothing,
        ])}
      </div>
    </div>
  `;
}

export function renderPersonCardGrid(
  cards: PersonCard[],
  roles: RoleOption[],
  options: PersonCardGridOptions = {},
) {
  const roleOrder = roles.map((role) => role.id);
  const groups = groupByRole(
    cards.map((card) => ({ id: card.personId, memberships: personOf(card)?.memberships, card })),
    roleOrder,
  );
  const sources = sourceMapFor(cards.map((card) => personOf(card)));

  return html`${groups.map((group) => renderGroup(group, sources, options))}`;
}
