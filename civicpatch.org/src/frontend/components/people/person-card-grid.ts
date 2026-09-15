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

// The url scheme a contact field's value needs prepended to become a link — email and phone
// render identically otherwise, so this is the only thing that told them apart.
const CONTACT_SCHEME: Record<string, string> = {
  emails: "mailto:",
  phones: "tel:",
};

export interface PersonCardGridOptions {
  onOpenPerson?: ((card: PersonCard) => void) | null;
  openPersonId?: string | null;
  renderEditor?: ((card: PersonCard) => unknown) | null;
}

function renderFieldValue(field: FieldSpec, list: string[]) {
  if (field.key === "urls")
    return list.map((url) =>
      renderLink(url, url, PERSON_LINK_TARGET, "pc-url"),
    );
  const scheme = CONTACT_SCHEME[field.key];
  if (scheme)
    return list.map(
      (value, i) =>
        html`${i > 0 ? ", " : ""}<a class="pc-link" href="${scheme}${value}"
          >${value}</a
        >`,
    );
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

// `label` now repeats the seat (post_label first, per `render(MembershipLabel(...))` on the
// backend) even though the group heading already names the role — the same duplication the
// office picker's own label input accepts, for the same reason: it needs to read on its own.
function subtitleFor(record: DiffRecord): string {
  return (
    (record?.memberships as { label: string | null }[] | undefined)?.[0]
      ?.label ?? ""
  );
}

function renderPerson(
  card: PersonCard,
  sources: SourceMap,
  { onOpenPerson, openPersonId }: PersonCardGridOptions,
) {
  const record = personOf(card);
  const name = record?.name || "(unnamed)";
  const subtitle = subtitleFor(record);
  const isOpen = onOpenPerson ? card.personId === openPersonId : false;
  const nameBlock = html`<span class="pc-name">${name}</span> ${subtitle
      ? html`<span class="pc-sub">${subtitle}</span>`
      : nothing}`;
  const openThisPerson = () => onOpenPerson?.(card);
  return html`
    <div
      class="rperson ${onOpenPerson ? "rperson--interactive" : ""} ${isOpen
        ? "rperson--open"
        : ""}"
    >
      ${onOpenPerson
        ? html`<button
            type="button"
            class="rperson__open"
            aria-label="${name}${subtitle ? `, ${subtitle}` : ""}"
            aria-expanded=${isOpen}
            @click=${openThisPerson}
          ></button>`
        : nothing}
      <span class="pc-av">
        <person-image
          .person=${record ?? {}}
          .size=${AVATAR_SIZE}
        ></person-image>
      </span>
      <span class="pc-ident">
        <span class="pc-open">${nameBlock}</span>
        ${renderFields(record, sources)}
      </span>
      ${onOpenPerson
        ? html`<i
            class="fa-solid fa-chevron-down pc-hint"
            aria-hidden="true"
          ></i>`
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
    <div class="rgroup" style="--group-cards: ${group.people.length}">
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
    cards.map((card) => ({
      id: card.personId,
      memberships: personOf(card)?.memberships,
      card,
    })),
    roleOrder,
  );
  const sources = sourceMapFor(cards.map((card) => personOf(card)));

  return html`<div class="rgroup-list">
    ${groups.map((group) => renderGroup(group, sources, options))}
  </div>`;
}
