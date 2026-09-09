
import { html, nothing } from "lit-html";
import { component, useState, useEffect, useCallback } from "haunted";
import { ref } from "lit-html/directives/ref.js";
import "../basic/modal.js";
import "./merge-picker.js";
import {
  applyMergePlan,
  chooseSurvivor,
  planMerge,
  setChoice,
  type MergeChoiceKey,
  type MergePlan,
} from "./merge-model.js";
import "./review-modal.css";
import "../person-editor/person-editor.css";
import {
  renderPersonEditor,
  renderPersonSummary,
  type PersonEditorProps,
} from "../person-editor/person-editor.js";
import {
  adjacentPeer,
  postsFor,
  personOf,
  proposalsByPersonId,
  STATUS_LABEL,
  type PersonCard,
  type ProposedChange,
} from "../people/person-cards.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import { focusOnMount } from "../../utils/focus-on-mount.js";
import { altArrowDirection } from "../../utils/keyboard.js";
import { type Post } from "../posts-list/posts-model.js";

export interface ReviewModalProps {
  cards: PersonCard[];
  changes?: ProposedChange[];
  posts: Post[];
  openPersonId: string | null;
  focusFieldKey: string | null;
  editor: EditorFactory;
  isReadOnly: boolean;
  onClose: () => void;
  mergePartner?: PersonCard | null;
  onMergeBack?: () => void;
  onMerge?: (
    survivorId: string,
    absorbedId: string,
    merged: Record<string, unknown>,
  ) => void;
}

export type EditorFactory = (card: PersonCard) => PersonEditorProps;

function ReviewModal(props: ReviewModalProps) {
  const {
    cards,
    changes,
    posts,
    openPersonId,
    focusFieldKey,
    editor,
    isReadOnly,
    onClose,
    mergePartner,
    onMergeBack,
    onMerge,
  } = props;
  const [personId, setPersonId] = useState<string | null>(null);
  const [mergePlan, setMergePlan] = useState<MergePlan | null>(null);
  const open = openPersonId !== null;
  const index = cards.findIndex((c) => c.personId === (personId ?? openPersonId));
  const card = cards[index];
  useEffect(() => {
    setMergePlan(null);
  }, [mergePartner?.personId]);
  const goTo = (nextId: string) => {
    if (!cards.some((c) => c.personId === nextId)) return;
    setPersonId(nextId);
  };
  useEffect(() => {
    setPersonId(open ? openPersonId : null);
  }, [openPersonId]);
  const focusOnOpen = useCallback(focusOnMount, [openPersonId, focusFieldKey]);
  const onKey = (e: KeyboardEvent) => {
    const direction = altArrowDirection(e);
    if (!direction || !card) return;
    const next = adjacentPeer(cards, card.personId, direction);
    if (next) goTo(next.personId);
  };
  if (!open || !card) return nothing;
  const editedCount = cards.filter((c) => c.surviving.length > 0).length;
  const proposals = proposalsByPersonId(changes ?? []);
  const editorProps = editor(card);
  const name = personOf(card)?.name || "(unnamed)";
  const head = html`
    <div class="review-modal__head">
      <span class="review-modal__who">${name}</span>
      ${renderPersonSummary({ ...editorProps, onReset: null })}
      <span class="review-modal__nav">
        <button
          class="review-modal__nav-btn"
          title="Previous person (Alt + Left)"
          ?disabled=${index <= 0}
          @click=${() => goTo(cards[index - 1].personId)}
        >
          <i class="fa-solid fa-arrow-left" aria-hidden="true"></i>
        </button>
        <span class="review-modal__pos">${index + 1} of ${cards.length}</span>
        <button
          class="review-modal__nav-btn"
          title="Next person (Alt + Right)"
          ?disabled=${index >= cards.length - 1}
          @click=${() => goTo(cards[index + 1].personId)}
        >
          <i class="fa-solid fa-arrow-right" aria-hidden="true"></i>
        </button>
      </span>
    </div>
  `;
  const content = html`
    <div class="review-modal__main" @keydown=${onKey}>
      <nav class="review-modal__people" aria-label="People in this review">
        <div class="review-modal__people-head">${editedCount} of ${cards.length} to review</div>
        ${cards.map((entry) => {
          const record = personOf(entry);
          const isOn = entry.personId === card.personId;
          return html`<button
            class="review-modal__person review-modal__person--${entry.status} ${isOn
              ? "review-modal__person--on"
              : ""}"
            aria-current=${isOn ? "true" : "false"}
            ${ref((el) => {
              if (isOn && el) (el as HTMLElement).scrollIntoView({ block: "nearest" });
            })}
            @click=${() => goTo(entry.personId)}
          >
            <span class="review-modal__person-who">
              <span class="review-modal__person-name">${record?.name || "(unnamed)"}</span>
              <span class="review-modal__person-sub"
                >${postsFor(entry, proposals, posts)}</span
              >
            </span>
            <span class="review-modal__person-meta">
              ${entry.issues.length
                ? html`<span class="review-modal__person-issue">!</span>`
                : entry.surviving.length
                  ? entry.surviving.length
                  : html`<span class="review-modal__person-done">✓</span>`}
            </span>
          </button>`;
        })}
      </nav>
      <div class="review-modal__body">
        ${head}
        <div class="person-editor-list">
          ${renderPersonEditor({
            ...editorProps,
            onReset: null,
            focusField: focusFieldKey ? { key: focusFieldKey, attach: focusOnOpen } : null,
          })}
        </div>
      </div>
    </div>
  `;
  const footer = html`
    <div class="review-modal__foot">
      <span>
        ${isReadOnly
          ? nothing
          : html`<button
              class="review-modal__revert"
              ?disabled=${!editorProps.onReset}
              @click=${() => editorProps.onReset?.()}
            >
              Revert this person
            </button>`}
        <button class="btn-sm" @click=${onClose}>${isReadOnly ? "Close" : "Done"}</button>
      </span>
    </div>
  `;
  const merging = !!mergePartner && !!onMergeBack && !!onMerge;
  const survivor = merging ? chooseSurvivor(card, mergePartner!) : null;
  const absorbed = !survivor
    ? null
    : survivor.personId === card.personId
      ? mergePartner!
      : card;
  const plan =
    survivor && absorbed ? (mergePlan ?? planMerge(survivor, absorbed)) : null;
  const chooseMerge = (fieldKey: string, choice: MergeChoiceKey) => {
    if (plan) setMergePlan(setChoice(plan, fieldKey, choice));
  };
  const commitMerge = () => {
    if (!plan || !survivor || !absorbed || !onMerge) return;
    onMerge(
      survivor.personId,
      absorbed.personId,
      applyMergePlan(plan, survivor, absorbed) as Record<string, unknown>,
    );
  };
  const survivorName = survivor ? (personOf(survivor)?.name ?? "this record") : "";
  const body = merging
    ? html`<merge-picker
        .anchor=${card}
        .survivor=${survivor}
        .absorbed=${absorbed}
        .plan=${plan}
        .onChoose=${chooseMerge}
        .onBack=${onMergeBack}
      ></merge-picker>`
    : content;
  const mergeFooter = html`
    <div class="review-modal__foot">
      <span>
        <button class="btn-sm secondary" @click=${onMergeBack}>Cancel</button>
        <button class="btn-sm" @click=${commitMerge}>Merge into ${survivorName}</button>
      </span>
    </div>
  `;
  return html`
    <div class="review-modal">
      <civ-modal
        .content=${body}
        .footer=${merging ? mergeFooter : footer}
        .modalProps=${{
          open: true,
          onClose,
          closeOnBackdropClick: true,
          ariaLabel: `Editing ${name}`,
        }}
      ></civ-modal>
      <p class="visually-hidden" role="status" aria-live="polite">
        ${name}, ${STATUS_LABEL[card.status] ?? card.status}, ${index + 1} of ${cards.length}
      </p>
    </div>
  `;
}

customElements.define(
  "review-modal",
  component(ReviewModal as unknown as () => unknown, { useShadowDOM: false }),
);
