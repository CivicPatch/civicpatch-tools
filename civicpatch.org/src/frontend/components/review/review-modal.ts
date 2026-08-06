// The edit modal (spec §6): the Detail rail mounted with one person, inside the
// existing <civ-modal> shell, built from the same rail props.
//
// Editing behaviour is therefore defined exactly once — this adds navigation
// around the rail, not a second editor. §21.3 is why it consumes
// <civ-modal> rather than baking the rail into a shell: merge will need an
// N-column body in the same frame.

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
import "../review-rail/review-rail.css";
import { renderPersonRail, type PersonRailProps } from "../review-rail/person-rail.js";
import { cardSubtitle, personOf, STATUS_LABEL, type ReviewCard } from "./review-cards.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";

export interface ReviewModalProps {
  // The set the modal was opened from, already narrowed by the caller — from
  // Overview that is the group the person was in. Stepping out of it would land
  // on someone with no visible fields, which is a dead end (§6).
  cards: ReviewCard[];
  openPersonId: string | null;
  focusFieldKey: string | null;
  rail: RailFactory;
  isReadOnly: boolean;
  onClose: () => void;
  // Opens the merge picker anchored on the person in view.
  // Merge is the modal's other screen, not a second dialog. Set means "show it".
  mergePartner?: ReviewCard | null;
  onMergeBack?: () => void;
  onMerge?: (
    survivorId: string,
    absorbedId: string,
    merged: Record<string, unknown>,
  ) => void;
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

  // Focus only on open. Navigating must not move focus, or pressing Next twice
  // fails — the second press lands on a control instead of the button. lit keys
  // refs by callback identity, so memoising on the open is what makes "only on
  // open" true: a fresh closure would re-fire on every render, and the controls
  // save on `input`, so every keystroke would snap focus back here.
  const focusOnOpen = useCallback(
    (el?: Element) => {
      // Element parts commit while the fragment is still detached, where
      // focus() is a no-op.
      if (el instanceof HTMLElement) queueMicrotask(() => el.focus());
    },
    [openPersonId, focusFieldKey],
  );

  // Alt-arrows, because plain arrows have to stay free for the caret.
  const onKey = (e: KeyboardEvent) => {
    if (!e.altKey) return;
    if (e.key === "ArrowLeft" && index > 0) goTo(cards[index - 1].personId);
    if (e.key === "ArrowRight" && index < cards.length - 1) goTo(cards[index + 1].personId);
  };

  if (!open || !card) return nothing;

  const editedCount = cards.filter((c) => c.surviving.length > 0).length;
  // Revert is the rail's own Reset, moved into the footer: one baseline — the
  // card as it loaded — so reopening cannot strand edits the roster calls dirty.
  const railProps = rail(card);

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
      <div class="review-modal__body">
        ${head}
        <!-- The rail's own Reset is dropped here: the footer is showing the same
             action, and two identical buttons read as two different ones. -->
        <div class="review-rail-list">
          ${renderPersonRail({
            ...railProps,
            onReset: null,
            focusField: focusFieldKey ? { key: focusFieldKey, attach: focusOnOpen } : null,
          })}
        </div>
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
              ?disabled=${!railProps.onReset}
              @click=${() => railProps.onReset?.()}
            >
              Revert this person
            </button>`}
        <button class="btn-sm" @click=${onClose}>${isReadOnly ? "Close" : "Done"}</button>
      </span>
    </div>
  `;

  // The merge plan lives here, not in merge-picker: its actions belong in the
  // dialog footer, where they cannot scroll out of reach, and the footer is
  // rendered from this side of civ-modal.
  const merging = !!mergePartner && !!onMergeBack && !!onMerge;

  // The survivor is computed, never chosen: the reviewer is asserting that two
  // records are one human, not deciding which id outlives the other.
  const survivor = merging ? chooseSurvivor(card, mergePartner!) : null;
  const absorbed = !survivor
    ? null
    : survivor.personId === card.personId
      ? mergePartner!
      : card;
  // Derived until the reviewer touches it, so reopening on a different pair
  // cannot show a stale plan.
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
      <!-- Escape and the backdrop behave as Done, not Cancel: discarding on a
           stray Escape is worse than keeping (§6.1). -->
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
