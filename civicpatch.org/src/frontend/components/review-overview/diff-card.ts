// One person, as a diff card — reuses the jurisdiction grid's `.rperson`/`.pc-*` shell
// (person-card-grid.css) rather than a bespoke row, adding what a diff needs on top: a
// status badge, a `<del>`/`<ins>` before/after per changed field, and the same open/pencil
// behavior the jurisdiction grid already has.

import { html, nothing } from "lit-html";
import "../person-image.js";
import { renderInlinePersonEditor } from "../person-editor/inline-editor.js";
import { renderCardShell } from "../people/person-card-grid.js";
import { ensureUrl } from "../fields/field-controls.js";
import { SOURCE_LINK_TARGET } from "../../utils/source-links.js";
import {
  postsFor,
  postNameFor,
  membershipLabelFor,
  movedNote,
  personOf,
  STATUS_LABEL,
  type MovedNote,
  type PersonCard,
} from "../people/person-cards.js";
import {
  diffValue,
  POST_FIELD,
  type SurvivingField,
} from "../fields/field-model.js";
import {
  acceptsByField,
  fieldLock,
  type FieldLock,
} from "../person-editor/field-provenance.js";
import { renderFieldValueDiff } from "./field-diff.js";
import {
  ATTENTION_COPY,
  attentionOf,
  issueTypesOf,
  STATUS_BADGE,
  visibleFields,
  type SourceMap,
} from "./overview-model.js";
import { type ReviewOverviewProps } from "./review-overview.js";
import { type ProposedChange } from "../../schemas/membership-proposal.js";

export function rowLabel(card: PersonCard): string {
  const parts = [
    personOf(card)?.name || "unnamed",
    STATUS_LABEL[card.status] ?? card.status,
  ];
  if (card.issues.length) {
    parts.push(`${card.issues.length} issue${card.issues.length === 1 ? "" : "s"}`);
  }
  return parts.join(", ");
}

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
  const isBlocking = attentionOf(card) === "error";
  const { icon, label } = ATTENTION_COPY.error;
  return html`${isBlocking
    ? html`<span class="review-row__attn review-row__attn--error">
        <i class="fa-solid fa-${icon}" aria-hidden="true"></i> ${label}
      </span>`
    : nothing}
    ${issueTypesOf(card).map(
      (type) => html`<span class="review-row__attn review-row__attn--issue"
        >${type}</span
      >`,
    )}`;
}

function renderStatusBadge(card: PersonCard, moved: MovedNote | null) {
  const badge = moved ? "Moved" : STATUS_BADGE[card.status];
  if (!badge) return nothing;
  return html`<span class="review-row__badge review-row__badge--${card.status}"
    >${badge}</span
  >`;
}

function renderFieldLock(lock: FieldLock | null) {
  return lock
    ? html`<i
        class="fa-solid fa-lock review-row__field-lock review-row__field-lock--${lock.state}"
        title="${lock.label}${lock.disclosure ? `. ${lock.disclosure}` : ""}"
      ></i>`
    : nothing;
}

// The post field is never a raw scraped value (see office-changes.ts/editor-field.ts's own
// comments on this) — `renderFieldValueDiff`'s generic diffValue-based rendering would show a
// raw post id, not a label. `movedNote`/`postNameFor` already resolve it to one, the same way
// the picker and the card subtitle do. Only the post itself is diffed here — the membership
// label is a second, independently-changing thing (office-changes.ts) and renders in its own
// row below, plainly, never compared against an old value.
function renderPostFieldValue(
  card: PersonCard,
  proposals: Map<string, ProposedChange[]>,
  props: ReviewOverviewProps,
) {
  const moved = movedNote(card, proposals, props.posts);
  if (moved) return html`<del>${moved.from}</del> <ins>${moved.to}</ins>`;
  return postNameFor(card, proposals, props.posts) || nothing;
}

function renderMembershipLabelRow(
  card: PersonCard,
  proposals: Map<string, ProposedChange[]>,
) {
  const label = membershipLabelFor(card, proposals);
  if (!label) return nothing;
  return html`<span class="pv">
    <span class="pvk">label</span>
    <span class="pvv">${label}</span>
  </span>`;
}

function renderFieldRow(
  surviving: SurvivingField,
  card: PersonCard,
  props: ReviewOverviewProps,
  proposals: Map<string, ProposedChange[]>,
) {
  const { field } = surviving;
  const record = personOf(card);
  const accepts = acceptsByField(props.assertions[card.personId] ?? []);
  const overrides = props.overriddenSourceValues[card.personId] ?? {};
  const lock = fieldLock(
    accepts.get(field.key),
    overrides[field.key],
    diffValue(record, field),
  );
  if (field.key === POST_FIELD) {
    return html`<span class="pv pv--post">
        <span class="pvk">${field.label.toLowerCase()}</span>
        <span class="pvv"
          >${renderFieldLock(lock)}${renderPostFieldValue(card, proposals, props)}</span
        >
      </span>
      ${renderMembershipLabelRow(card, proposals)}`;
  }
  const value = renderFieldValueDiff(field, surviving.state, card.oldRecord, card.newRecord);
  return html`<span class="pv">
    <span class="pvk">${field.label.toLowerCase()}</span>
    <span class="pvv">${renderFieldLock(lock)}${value}</span>
  </span>`;
}

export function renderDiffCard(
  card: PersonCard,
  props: ReviewOverviewProps,
  sources: SourceMap,
  proposals: Map<string, ProposedChange[]>,
) {
  const record = personOf(card);
  const moved = movedNote(card, proposals, props.posts);
  const fields = visibleFields(card);
  const isOpen = card.personId === props.openPersonId;
  return renderCardShell(
    {
      card,
      ariaLabel: rowLabel(card),
      isOpen,
      onOpenPerson: (c: PersonCard) =>
        props.onOpenPerson(c.personId, fields[0]?.field.key ?? null),
      editorId: `review-person-${card.personId}`,
      extraClass: `review-row--${card.status}`,
    },
    html`
      <span class="pc-av">
        <person-image .person=${record ?? {}} .size=${"4rem"}></person-image>
      </span>
      <span class="pc-ident">
        <span class="pc-open">
          <span class="pc-name">${record?.name || "(unnamed)"}</span>
          ${renderStatusBadge(card, moved)}
          ${renderAttention(card)}
        </span>
        <span class="pc-vals">
          ${fields.map((field) => renderFieldRow(field, card, props, proposals))}
        </span>
        <span class="review-row__sources">${renderSources(card, sources)}</span>
      </span>
      <i class="fa-solid fa-chevron-down pc-hint" aria-hidden="true"></i>
    `,
  );
}

export function renderInlineEditor(card: PersonCard, props: ReviewOverviewProps) {
  return renderInlinePersonEditor({
    card,
    openPersonId: props.openPersonId,
    editorFor: props.editorFor,
    idPrefix: "review-person-",
  });
}

export function renderFold(
  card: PersonCard,
  props: ReviewOverviewProps,
  proposals: Map<string, ProposedChange[]>,
) {
  const record = personOf(card);
  const isOpen = card.personId === props.openPersonId;
  return html`
    <span class="review-fold ${isOpen ? "review-fold--open" : ""}">
      <button
        class="review-fold__open"
        aria-label=${rowLabel(card)}
        aria-expanded=${isOpen}
        @click=${() => props.onOpenPerson(card.personId, null)}
      >
        <person-image
          .person=${record}
          .size=${"2.1rem"}
        ></person-image>
        <span class="review-fold__who">
          <span class="review-fold__name">${record?.name || "(unnamed)"}</span>
          <span class="review-fold__meta">
            <span class="review-fold__sub"
              >${postsFor(card, proposals, props.posts) || nothing}</span
            >
            ${renderAttention(card)}
          </span>
        </span>
      </button>
      <i class="fa-solid fa-pen-to-square review-row__hint" aria-hidden="true"></i>
    </span>
  `;
}
