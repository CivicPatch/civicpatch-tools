import { html, nothing } from "lit-html";
import "../person-image.js";
import "./person-card-grid.css";
import {
  type PersonCard,
  personOf,
  cardKey,
  DEPARTING,
} from "./person-cards.js";
import { postName, type RoleOption } from "../posts-list/posts-model.js";
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
import { groupByRole } from "./person-card-grid-model.js";

const AVATAR_SIZE = "4rem";

// The url scheme a contact field's value needs prepended to become a link — email and phone
// render identically otherwise, so this is the only thing that told them apart.
const CONTACT_SCHEME: Record<string, string> = {
  emails: "mailto:",
  phones: "tel:",
};

export interface PersonCardGridOptions {
  onOpenPerson?: ((card: PersonCard) => void) | null;
  openCardKey?: string | null;
  renderEditor?: ((card: PersonCard) => unknown) | null;
  // Matches whatever prefix the caller's own renderEditor gives the inline editor's id, so the
  // card's button can point `aria-controls` at it. No prefix, no `aria-controls` — a caller
  // that never opens an editor (a read-only grid) has nothing to point at.
  idPrefix?: string;
}

export interface CardShellOptions {
  card: PersonCard;
  ariaLabel: string;
  isOpen: boolean;
  onOpenPerson?: ((card: PersonCard) => void) | null;
  editorId?: string;
  // An extra class beyond `rperson`/`rperson--interactive`/`rperson--open` — review's diff
  // status tint (`review-row--${status}`), which plain jurisdiction cards have no equivalent
  // of.
  extraClass?: string;
}

// The one `.rperson`/`.rperson__open` shell, shared by the jurisdiction roster and review's
// diff cards — content (avatar, name, fields, whatever a caller needs) is the only thing that
// differs between them. `.rperson__open` is pointer-events: none (person-card-grid.css) so a
// mouse click reaches the real content underneath instead of the invisible button, which is
// what lets a name or field value be selected/copied. This shell's own click handler is what
// actually opens the editor: it catches that bubbled click (mouse) and the button's own
// synthetic one (Enter/Space, keyboard), but not a drag-to-select (an active selection means
// the click ended a selection, not a click) or a real link's own click (it navigates; this
// must not also open the card).
export function renderCardShell(
  {
    card,
    ariaLabel,
    isOpen,
    onOpenPerson,
    editorId,
    extraClass = "",
  }: CardShellOptions,
  content: unknown,
) {
  const handleCardClick = (e: MouseEvent) => {
    if (!onOpenPerson) return;
    if (window.getSelection()?.toString()) return;
    if ((e.target as HTMLElement)?.closest?.("a")) return;
    onOpenPerson(card);
  };
  return html`
    <div
      class="rperson ${onOpenPerson ? "rperson--interactive" : ""} ${isOpen
        ? "rperson--open"
        : ""} ${extraClass}"
      @click=${handleCardClick}
    >
      ${onOpenPerson
        ? html`<button
            type="button"
            class="rperson__open"
            aria-label=${ariaLabel}
            aria-expanded=${isOpen}
            aria-controls=${editorId || nothing}
          ></button>`
        : nothing}
      ${content}
    </div>
  `;
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

interface Subtitle {
  postLabel: string;
  membershipLabel: string;
}

// Two lines, not one: `label` used to already include the post's own name (`render
// (MembershipLabel(...))` on the backend composed it seat-first) — now it is only what the
// occupant's own labels said beyond it, so the two render separately rather than glued
// together into a string that repeated the group heading's own role.
function subtitleFor(record: DiffRecord): Subtitle {
  const held = (
    record?.memberships as
      | { post_label: string; label: string | null }[]
      | undefined
  )?.[0];
  return {
    postLabel: held ? postName(held) : "",
    membershipLabel: held?.label ?? "",
  };
}

function renderPerson(
  card: PersonCard,
  sources: SourceMap,
  { onOpenPerson, openCardKey, idPrefix }: PersonCardGridOptions,
) {
  const record = personOf(card);
  const name = record?.name || "(unnamed)";
  const { postLabel, membershipLabel } = subtitleFor(record);
  // By card key, not person id: a person on two bodies has a row in each, and only the one
  // that was clicked opens. The two are the same string for a card with no body.
  const isOpen = onOpenPerson ? cardKey(card) === openCardKey : false;
  const ariaSubtitle = [postLabel, membershipLabel].filter(Boolean).join(", ");
  const nameBlock = html`<span class="pc-name">${name}</span> ${postLabel
      ? html`<span class="pc-sub">${postLabel}</span>`
      : nothing}
    ${membershipLabel
      ? html`<span class="pc-sub">${membershipLabel}</span>`
      : nothing}`;
  return renderCardShell(
    {
      card,
      ariaLabel: `${name}${ariaSubtitle ? `, ${ariaSubtitle}` : ""}`,
      isOpen,
      onOpenPerson,
      editorId: idPrefix ? `${idPrefix}${cardKey(card)}` : undefined,
      extraClass: DEPARTING.has(card.status) ? "rperson--removing" : "",
    },
    html`
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
    `,
  );
}

function renderGroupHead(roleLabel: string, count: number) {
  return html`
    <div class="rgrouphead">
      ${roleLabel}${count > 1
        ? html` <span class="sub">${count}</span>`
        : nothing}
    </div>
  `;
}

// A card's own row never moves or resizes for an editor opening — a group can't widen either
// (person-card-grid.css's own comment on why: it'd change how many groups fit a `.rgroup-list`
// line, bumping *other* groups down a row even though nothing about their own size changed).
// So the group containing the open card splits in three, right around it: everything up to and
// including the open card renders exactly as it always would have (same box, same heading, same
// positions); the editor follows as a `.rgroup-list`-level sibling (`flex: 1 0 100%` there is
// what gives it a full line without touching any card's size); whatever comes after in the same
// group starts fresh in a second, headingless box of its own on the row after that. Nothing
// before the open card is touched at all — only what comes after it moves.
//
// `renderCards` renders whichever subset of `items` it's given in whatever internal shape a
// caller needs (a plain map for the jurisdiction grid; runs of folded strips and diff cards for
// review) — this function only owns where the group breaks, not how a card renders.
export function renderRoleGroup<T>(
  roleLabel: string,
  items: T[],
  keyOf: (item: T) => string,
  renderCards: (items: T[]) => unknown,
  openCardKey: string | null | undefined,
  renderEditor: ((item: T) => unknown) | null | undefined,
): unknown {
  if (!items.length) return nothing;
  const openIndex =
    renderEditor && openCardKey
      ? items.findIndex((item) => keyOf(item) === openCardKey)
      : -1;
  if (openIndex === -1) {
    return html`
      <div class="rgroup" style="--group-cards: ${items.length}">
        ${renderGroupHead(roleLabel, items.length)}
        <div class="rgrid">${renderCards(items)}</div>
      </div>
    `;
  }
  const upToOpen = items.slice(0, openIndex + 1);
  const after = items.slice(openIndex + 1);
  // Both halves keep the whole group's width: a narrower first half fits beside the group
  // before it and jumps up a line.
  return html`
    <div class="rgroup" style="--group-cards: ${items.length}">
      ${renderGroupHead(roleLabel, items.length)}
      <div class="rgrid">${renderCards(upToOpen)}</div>
    </div>
    ${renderEditor!(items[openIndex])}
    ${after.length
      ? html`
          <div class="rgroup" style="--group-cards: ${items.length}">
            <div class="rgrid">${renderCards(after)}</div>
          </div>
        `
      : nothing}
  `;
}

export function renderPersonCardGrid(
  cards: PersonCard[],
  roles: RoleOption[],
  options: PersonCardGridOptions = {},
) {
  const { openCardKey, renderEditor } = options;
  const roleOrder = roles.map((role) => role.id);
  const groups = groupByRole(
    cards.map((card) => ({
      id: card.personId,
      memberships: personOf(card)?.memberships?.map((membership) => ({
        role_id: membership.role_id,
        role_label: membership.role_label,
        post_label: membership.post_label,
        membership_label: membership.label,
      })),
      card,
    })),
    roleOrder,
  );
  const sources = sourceMapFor(cards.map((card) => personOf(card)));

  return html`<div class="rgroup-list">
    ${groups.map((group) =>
      renderRoleGroup(
        group.roleLabel,
        group.people,
        ({ card }) => cardKey(card),
        (people) =>
          people.map(({ card }) => renderPerson(card, sources, options)),
        openCardKey,
        renderEditor && ((item) => renderEditor(item.card)),
      ),
    )}
  </div>`;
}
