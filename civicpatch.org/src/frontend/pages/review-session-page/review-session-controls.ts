import { html } from "lit-html";
import { component } from "haunted";

export interface Progress {
  entryNumber: number;
  hasPrev: boolean;
  resolvedEntryNumbers: Set<number>;
  savedEntryNumbers: Set<number>;
  failedEntryNumbers: Set<number>;
  frontierEntry: number;
  total: number;
}

// Where the reviewer is in the queue, and how they move around it. The actions
// that act on the card's data (publish, save, close) belong to the card, which
// owns that data — this is navigation only.
//
// The host dissolves (`display: contents`) so .review-page__step-nav is a direct
// flex item of the header; on narrow screens the header dissolves too and the
// step-nav is what stays sticky.
const BACK_EVENT = "back";
const ADVANCE_EVENT = "advance";
const NAVIGATE_TO_EVENT = "navigate-to";

type ReviewSessionControlsHost = HTMLElement & {
  progress: Progress;
  hasSession: boolean;
  hasNext: boolean;
};

function ReviewSessionControls(host: ReviewSessionControlsHost) {
  const { progress, hasSession, hasNext } = host;
  const { entryNumber, hasPrev, resolvedEntryNumbers, savedEntryNumbers, failedEntryNumbers, frontierEntry, total } = progress ?? {};
  const displayMax = hasSession ? total : entryNumber;

  function getDotStatus(n: number) {
    if (n === entryNumber) return "current";
    if (failedEntryNumbers.has(n)) return "failed";
    if (resolvedEntryNumbers.has(n)) return "resolved";
    if (savedEntryNumbers.has(n)) return "saved";
    if (n <= frontierEntry) return "deferred";
    return "future";
  }

  const handleBack = () =>
    host.dispatchEvent(new CustomEvent(BACK_EVENT, { bubbles: true, composed: true }));

  const handleAdvance = () =>
    host.dispatchEvent(new CustomEvent(ADVANCE_EVENT, { bubbles: true, composed: true }));

  const handleNavigateTo = (entry: number) =>
    host.dispatchEvent(
      new CustomEvent(NAVIGATE_TO_EVENT, { detail: { entry_number: entry }, bubbles: true, composed: true }),
    );

  // A deeplinked card has no queue to step through, but the empty nav still
  // holds the header's left column so the actions stay right-aligned.
  if (!hasSession) return html`<div class="review-page__step-nav"></div>`;

  return html`
    <div class="review-page__step-nav">
      <button class="btn-sm review-page__back-btn" @click=${handleBack} ?disabled=${!hasPrev}><i class="fa-solid fa-arrow-left"></i> Back</button>
      <span class="review-page__progress">${entryNumber} of ${displayMax}</span>
      <div class="review-page__dots">
        ${Array.from({ length: total }, (_, i) => i + 1).map((n) => {
          const status = getDotStatus(n);
          return html`<button
            class="review-page__dot review-page__dot--${status}"
            ?disabled=${status === "future" || status === "current"}
            @click=${() => handleNavigateTo(n)}
          ></button>`;
        })}
      </div>
      <button class="btn-sm review-page__next-btn" @click=${handleAdvance} ?disabled=${!hasNext}>Next <i class="fa-solid fa-arrow-right"></i></button>
    </div>
  `;
}

customElements.define(
  "review-session-controls",
  component(ReviewSessionControls as unknown as () => unknown, { useShadowDOM: false }),
);
