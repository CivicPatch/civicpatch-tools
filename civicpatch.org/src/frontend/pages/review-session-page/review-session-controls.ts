import { html } from "lit-html";
import { component } from "haunted";

export interface Progress {
  entryNumber: number;
  hasPrev: boolean;
  resolvedEntryNumbers: Set<number>;
  failedEntryNumbers: Set<number>;
  frontierEntry: number;
  total: number;
}

interface ReviewSessionControlsProps {
  progress: Progress;
  hasSession: boolean;
  hasNext: boolean;
  isReadOnly: boolean;
  isClosingPr: boolean;
  isDirty: boolean;
  onEndSession: () => void;
  onBack: () => void;
  onNavigateTo: (n: number) => void;
  onAdvance: () => void;
  onClosePr: () => void;
  onMerge: () => void;
}

function ReviewSessionControls({
  progress,
  hasSession,
  hasNext,
  isReadOnly,
  isClosingPr,
  isDirty,
  onEndSession,
  onBack,
  onNavigateTo,
  onAdvance,
  onClosePr,
  onMerge,
}: ReviewSessionControlsProps) {
  const { entryNumber, hasPrev, resolvedEntryNumbers, failedEntryNumbers, frontierEntry, total } = progress ?? {};
  const displayMax = hasSession ? total : entryNumber;

  function getDotStatus(n: number) {
    if (n === entryNumber) return "current";
    if (failedEntryNumbers.has(n)) return "failed";
    if (resolvedEntryNumbers.has(n)) return "resolved";
    if (n <= frontierEntry) return "deferred";
    return "future";
  }

  return html`
    <div class="review-page__header">
      ${!hasSession ? html`<div class="review-page__step-nav"></div>` : html`
      <div class="review-page__step-nav">
        <button class="btn-sm review-page__back-btn" @click=${onBack} ?disabled=${!hasPrev}><i class="fa-solid fa-arrow-left"></i> Back</button>
        <span class="review-page__progress">${entryNumber} of ${displayMax}</span>
        <div class="review-page__dots">
          ${Array.from({ length: total }, (_, i) => i + 1).map((n) => {
            const status = getDotStatus(n);
            return html`<button
              class="review-page__dot review-page__dot--${status}"
              ?disabled=${status === "future" || status === "current"}
              @click=${() => onNavigateTo(n)}
            ></button>`;
          })}
        </div>
        <button class="btn-sm review-page__next-btn" @click=${() => onAdvance()} ?disabled=${!hasNext}>Next <i class="fa-solid fa-arrow-right"></i></button>
      </div>
      `}
      <div class="review-page__actions">
        ${isReadOnly ? "" : html`
        <button class="btn-sm review-page__merge-btn btn-gradient" @click=${onMerge}>
          ${isDirty ? "Save and Publish" : "Publish"}
        </button>
        <button class="btn-sm destructive" @click=${onClosePr} ?disabled=${isClosingPr}>
          ${isClosingPr ? "Closing..." : "Close PR"}
        </button>
        `}
        <button class="btn-sm review-page__end-btn" @click=${onEndSession}>${hasSession ? "End session" : "Exit"}</button>
      </div>
    </div>
  `;
}

customElements.define("review-session-controls", component(ReviewSessionControls, { useShadowDOM: false }));
