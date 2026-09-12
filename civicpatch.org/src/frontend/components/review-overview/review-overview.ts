import { html, nothing } from "lit-html";
import { component } from "haunted";
import "../person-image.js";
import "./review-overview.css";
import { renderPersonRow } from "../people/person-row.js";
import { renderInlinePersonEditor } from "../person-editor/inline-editor.js";
import { type PersonEditorProps } from "../person-editor/person-editor.js";
import { type Post } from "../posts-list/posts-model.js";
import { ensureUrl } from "../fields/field-controls.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { SOURCE_LINK_TARGET } from "../../utils/source-links.js";
import {
  postsFor,
  proposalsByPersonId,
  type ProposedChange,
  DEPARTING,
  movedNote,
  personOf,
  PersonStatus,
  STATUS_LABEL,
  type PersonCard,
} from "../people/person-cards.js";
import { diffValue, type SurvivingField } from "../fields/field-model.js";
import {
  acceptsByField,
  fieldLock,
  type PersonAssertion,
} from "../person-editor/field-provenance.js";
import {
  ATTENTION_COPY,
  attentionOf,
  fieldClass,
  FIELD_CAP,
  isDated,
  isVerified,
  runsOf,
  sourceMapFor,
  STATUS_BADGE,
  tallyOf,
  visibleFields,
  type SourceMap,
} from "./overview-model.js";

interface ReviewOverviewProps {
  cards: PersonCard[];
  changes?: ProposedChange[];
  isReadOnly: boolean;
  onOpenPerson: (personId: string, fieldKey: string | null) => void;
  onAdd?: () => void;
  openPersonId: string | null;
  editorFor: (card: PersonCard) => PersonEditorProps;
  posts: Post[];
  assertions: Record<string, PersonAssertion[]>;
  overriddenSourceValues: Record<string, Record<string, unknown>>;
}

function rowLabel(card: PersonCard): string {
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
  const attention = attentionOf(card);
  if (!attention) return nothing;
  const { icon, label } = ATTENTION_COPY[attention];
  return html`<span class="review-row__attn review-row__attn--${attention}">
    <i class="fa-solid fa-${icon}" aria-hidden="true"></i> ${label}
  </span>`;
}

function renderFields(card: PersonCard, props: ReviewOverviewProps) {
  if (DEPARTING.has(card.status)) return nothing;
  const ranked = visibleFields(card);
  const shown = ranked.slice(0, FIELD_CAP);
  const hidden = ranked.length - shown.length;
  const record = personOf(card);
  const accepts = acceptsByField(props.assertions[card.personId] ?? []);
  const overrides = props.overriddenSourceValues[card.personId] ?? {};
  return shown.map((field) => {
    const lock = fieldLock(
      accepts.get(field.field.key),
      overrides[field.field.key],
      diffValue(record, field.field),
    );
    return html`<span
      class="review-row__field review-row__field--${fieldClass(field)}"
      >${lock
        ? html`<i
            class="fa-solid fa-lock review-row__field-lock review-row__field-lock--${lock.state}"
            title="${lock.label}${lock.disclosure ? `. ${lock.disclosure}` : ""}"
          ></i>`
        : nothing}${field.field.label}</span
    >`;
  }).concat(
    hidden > 0
      ? [html`<span class="review-row__more">+${hidden} more</span>`]
      : [],
  );
}

function renderRow(
  card: PersonCard,
  props: ReviewOverviewProps,
  sources: SourceMap,
  proposals: Map<string, ProposedChange[]>,
) {
  const moved = movedNote(card, proposals, props.posts);
  const badge = moved ? "Moved" : STATUS_BADGE[card.status];
  const firstField = visibleFields(card)[0]?.field.key ?? null;
  return renderPersonRow({
    record: personOf(card),
    name: personOf(card)?.name || "(unnamed)",
    subtitle: postsFor(card, proposals, props.posts) || "",
    ariaLabel: rowLabel(card),
    onOpen: () => props.onOpenPerson(card.personId, firstField),
    modifier: card.status,
    isOpen: card.personId === props.openPersonId,
    controlsId: `review-person-${card.personId}`,
    meta: html`
      ${renderAttention(card)}
      ${badge
        ? html`<span class="review-row__badge review-row__badge--${card.status}"
            >${badge}</span
          >`
        : nothing}
      ${moved
        ? html`<span class="review-row__moved">${moved.from} → ${moved.to}</span>`
        : nothing}
      ${!isVerified(card, props.assertions)
        ? html`<span
            class="review-row__badge review-row__badge--unverified"
            title="No human has published any field on this record"
            >unverified</span
          >`
        : nothing}
      ${!isDated(card)
        ? html`<span
            class="review-row__badge review-row__badge--unverified"
            title="No term dates on file, so we cannot say whether they still hold this seat"
            >no term</span
          >`
        : nothing}
      ${renderFields(card, props)}
      <span class="review-row__sources">${renderSources(card, sources)}</span>
    `,
  });
}

function renderInlineEditor(card: PersonCard, props: ReviewOverviewProps) {
  return renderInlinePersonEditor({
    card,
    openPersonId: props.openPersonId,
    editorFor: props.editorFor,
    idPrefix: "review-person-",
  });
}

function renderFold(
  card: PersonCard,
  props: ReviewOverviewProps,
  proposals: Map<string, ProposedChange[]>,
) {
  const record = personOf(card);
  return html`
    <span class="review-fold">
      <button
        class="review-fold__open"
        aria-label=${rowLabel(card)}
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

function ReviewOverview(props: ReviewOverviewProps) {
  const { cards, isReadOnly, onAdd } = props;
  const proposals = proposalsByPersonId(props.changes ?? []);
  const list = cards ?? [];
  const sources = sourceMapFor(list);

  return html`
    <div class="review-overview">
      ${renderTally(list)}
      ${list.length
        ? html`<div class="review-overview__list">
            ${runsOf(list).map((run) =>
              run.folded
                ? html`<div class="review-overview__strip">
                      ${run.cards.map((card) => renderFold(card, props, proposals))}
                    </div>
                    ${run.cards.map((card) => renderInlineEditor(card, props))}`
                : run.cards.flatMap((card) => [
                    renderRow(card, props, sources, proposals),
                    renderInlineEditor(card, props),
                  ]),
            )}
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
