// The edit modal (spec §6): the Detail rail mounted with one person, inside the
// existing <civ-modal> shell, wired to the same onPersonSave.
//
// Editing behaviour is therefore defined exactly once — this adds navigation and
// an undo buffer around the rail, not a second editor. §21.3 is why it consumes
// <civ-modal> rather than baking the rail into a shell: merge will need an
// N-column body in the same frame.

import { html, nothing } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { ref } from "lit-html/directives/ref.js";
import "../basic/modal.js";
import "../person-image.js";
import "./review-modal.css";
import "../review-rail/review-rail.css";
import { withDisplayImage } from "./field-controls.js";
import { renderPersonRail, type PersonRailProps } from "../review-rail/person-rail.js";
import { cardSubtitle, personOf, STATUS_LABEL, type ReviewCard } from "./review-cards.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import {
  takeSnapshot,
  planRevert,
  isUnchangedSince,
  type PersonSnapshot,
} from "./person-snapshot.js";

export interface ReviewModalProps {
  // The set the modal was opened from, already narrowed by the caller — from
  // Overview that is the group the person was in. Stepping out of it would land
  // on someone with no visible fields, which is a dead end (§6).
  cards: ReviewCard[];
  openPersonId: string | null;
  focusFieldKey: string | null;
  rail: RailFactory;
  removedIds: Set<string>;
  restoredIds: Set<string>;
  isReadOnly: boolean;
  onClose: () => void;
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
  onRemove: (id: string) => void;
  onUnremove: (id: string) => void;
  onRestore: (person: any) => void;
  onUndoRestore: (id: string) => void;
}

// The caller already knows how to build a rail for a card (it does so for
// Detail), so it hands that over rather than this rebuilding it — one definition
// of what a person's row looks like.
export type RailFactory = (card: ReviewCard) => PersonRailProps;

function ReviewModal(props: ReviewModalProps) {
  const {
    cards,
    openPersonId,
    focusFieldKey,
    rail,
    isReadOnly,
    removedIds,
    restoredIds,
    onClose,
    onPersonSave,
    onRemove,
    onUnremove,
    onRestore,
    onUndoRestore,
  } = props;

  const [personId, setPersonId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<PersonSnapshot | null>(null);

  const open = openPersonId !== null;
  const index = cards.findIndex((c) => c.personId === (personId ?? openPersonId));
  const card = cards[index];

  // Re-snapshot on every move, so Revert only ever undoes work on the person in
  // view — not the reviewer's earlier edits elsewhere (§6.1).
  const goTo = (nextId: string) => {
    const next = cards.find((c) => c.personId === nextId);
    if (!next) return;
    setPersonId(nextId);
    setSnapshot(takeSnapshot(nextId, next.newRecord, removedIds, restoredIds));
  };

  useEffect(() => {
    if (!open || !openPersonId) {
      setPersonId(null);
      setSnapshot(null);
      return;
    }
    setPersonId(openPersonId);
    const opened = cards.find((c) => c.personId === openPersonId);
    setSnapshot(takeSnapshot(openPersonId, opened?.newRecord, removedIds, restoredIds));
  }, [openPersonId]);

  // Focus only on open. Navigating must not move focus, or pressing Next twice
  // fails — the second press lands on a control instead of the button. The
  // target may be an <input> OR a <select> (Division), so both are candidates.
  const focusOnOpen = (el: Element | undefined) => {
    if (!el || !focusFieldKey) return;
    queueMicrotask(() => {
      const row = (el as HTMLElement).querySelector(
        `.review-rail__field [data-field="${focusFieldKey}"]`,
      );
      const control = (row ?? (el as HTMLElement).querySelector(".review-rail__field")) as
        | HTMLElement
        | null;
      control?.querySelector<HTMLElement>("input, select")?.focus();
    });
  };

  const revert = () => {
    if (!snapshot || !card) return;
    const plan = planRevert(snapshot, removedIds, restoredIds);
    if (plan.updates) onPersonSave(snapshot.personId, plan.updates);
    if (plan.delete) onRemove(snapshot.personId);
    if (plan.undelete) onUnremove(snapshot.personId);
    if (plan.restore) onRestore(snapshot.record);
    if (plan.undoRestore) onUndoRestore(snapshot.personId);
  };

  // Alt-arrows, because plain arrows have to stay free for the caret.
  const onKey = (e: KeyboardEvent) => {
    if (!e.altKey) return;
    if (e.key === "ArrowLeft" && index > 0) goTo(cards[index - 1].personId);
    if (e.key === "ArrowRight" && index < cards.length - 1) goTo(cards[index + 1].personId);
  };

  if (!open || !card) return nothing;

  const editedCount = cards.filter((c) => c.surviving.length > 0).length;
  const canRevert =
    snapshot && !isUnchangedSince(snapshot, card.newRecord, removedIds, restoredIds);

  const name = personOf(card)?.name || "(unnamed)";

  // Rendered inside the body rather than passed as civ-modal's `title`: `title`
  // is a native HTMLElement property, so setting it to anything but a string
  // coerces — a template arrived as "[object Object]".
  const head = html`
    <div class="review-modal__head">
      <span>${name}</span>
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
            <person-image
              .person=${withDisplayImage(record)}
              .size=${"1.4rem"}
            ></person-image>
            <span class="review-modal__person-who">
              <span class="review-modal__person-name">${record?.name || "(unnamed)"}</span>
              <span class="review-modal__person-sub"
                >${cardSubtitle(entry, divisionOcdidToFriendly)}</span
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
      <div class="review-modal__body" ${ref(focusOnOpen)}>
        ${head}
        <div class="review-rail-list">${renderPersonRail(rail(card))}</div>
      </div>
    </div>
  `;

  // Read-only opens and navigates, but offers nothing to undo — there is
  // nothing to have changed, so Revert would be a button that never applies.
  const footer = html`
    <div class="review-modal__foot">
      <span>
        ${isReadOnly
          ? nothing
          : html`<button
              class="review-modal__revert"
              ?disabled=${!canRevert}
              @click=${revert}
            >
              Revert this person
            </button>`}
        <button class="btn-sm" @click=${onClose}>${isReadOnly ? "Close" : "Done"}</button>
      </span>
    </div>
  `;

  return html`
    <div class="review-modal">
      <!-- Escape and the backdrop behave as Done, not Cancel: discarding on a
           stray Escape is worse than keeping (§6.1). -->
      <civ-modal
        .content=${content}
        .footer=${footer}
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
