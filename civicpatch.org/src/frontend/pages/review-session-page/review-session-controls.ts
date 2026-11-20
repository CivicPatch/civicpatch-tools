import { html, nothing } from "lit-html";
import { component } from "haunted";
import "../../components/review-sidebar/review-sidebar-trigger.js";

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
// The host dissolves (`display: contents`) so .review-session__step-nav is a direct
// flex item of the header; on narrow screens the header dissolves too and the
// step-nav is what stays sticky.
const BACK_EVENT = "back";
const ADVANCE_EVENT = "advance";
const NAVIGATE_TO_EVENT = "navigate-to";

const DotStatus = Object.freeze({
  CURRENT: "current",
  FAILED: "failed",
  RESOLVED: "resolved",
  SAVED: "saved",
  DEFERRED: "deferred",
  FUTURE: "future",
} as const);

type DotStatusKey = (typeof DotStatus)[keyof typeof DotStatus];

const DOT_LABEL: Record<DotStatusKey, string> = {
  [DotStatus.CURRENT]: "this entry",
  [DotStatus.FAILED]: "save failed",
  [DotStatus.RESOLVED]: "done",
  [DotStatus.SAVED]: "saved, not published",
  [DotStatus.DEFERRED]: "skipped",
  [DotStatus.FUTURE]: "not reached yet",
};

// The checklist trigger rides in here rather than in .review-session__actions
// because the step-nav is the only part of the header that stays sticky below
// 768px — the header itself becomes `display: contents` and the action buttons
// drop into normal flow and scroll away. The trigger is the drawer's only
// affordance, so it cannot be allowed to scroll off. Two forwarded numbers, no
// checklist logic.
type ReviewSessionControlsHost = HTMLElement & {
  progress: Progress;
  hasSession: boolean;
  hasNext: boolean;
  checklistDone: number;
  checklistTotal: number;
};

function ReviewSessionControls(host: ReviewSessionControlsHost) {
  const { progress, hasSession, hasNext, checklistDone, checklistTotal } = host;
  const { entryNumber, hasPrev, resolvedEntryNumbers, savedEntryNumbers, failedEntryNumbers, frontierEntry, total } = progress ?? {};
  const displayMax = hasSession ? total : entryNumber;

  function getDotStatus(n: number): DotStatusKey {
    if (n === entryNumber) return DotStatus.CURRENT;
    if (failedEntryNumbers.has(n)) return DotStatus.FAILED;
    if (resolvedEntryNumbers.has(n)) return DotStatus.RESOLVED;
    if (savedEntryNumbers.has(n)) return DotStatus.SAVED;
    if (n <= frontierEntry) return DotStatus.DEFERRED;
    return DotStatus.FUTURE;
  }

  const handleBack = () =>
    host.dispatchEvent(new CustomEvent(BACK_EVENT, { bubbles: true, composed: true }));

  const handleAdvance = () =>
    host.dispatchEvent(new CustomEvent(ADVANCE_EVENT, { bubbles: true, composed: true }));

  const handleNavigateTo = (entry: number) =>
    host.dispatchEvent(
      new CustomEvent(NAVIGATE_TO_EVENT, { detail: { entry_number: entry }, bubbles: true, composed: true }),
    );

  const checklistTrigger = html`
    <review-sidebar-trigger
      .done=${checklistDone}
      .total=${checklistTotal}
    ></review-sidebar-trigger>
  `;

  // A deeplinked card has no queue to step through, but the nav still holds the
  // header's left column so the actions stay right-aligned — and it still needs
  // the checklist trigger, since arriving from a PR link is a normal way in.
  if (!hasSession) {
    return html`<div class="review-session__step-nav">${checklistTrigger}</div>`;
  }

  return html`
    <div class="review-session__step-nav">
      <button class="btn-sm review-session__back-btn" @click=${handleBack} ?disabled=${!hasPrev}><i class="fa-solid fa-arrow-left"></i> Back</button>
      <span class="review-session__progress">${entryNumber} of ${displayMax}</span>
      <div class="review-session__dots">
        ${Array.from({ length: total }, (_, i) => i + 1).map((n) => {
          const status = getDotStatus(n);
          const label = `Entry ${n} of ${total}: ${DOT_LABEL[status]}`;
          return html`<button
            class="review-session__dot review-session__dot--${status}"
            aria-label=${label}
            title=${label}
            aria-current=${status === DotStatus.CURRENT ? "step" : nothing}
            ?disabled=${status === DotStatus.FUTURE || status === DotStatus.CURRENT}
            @click=${() => handleNavigateTo(n)}
          ></button>`;
        })}
      </div>
      <button class="btn-sm review-session__next-btn" @click=${handleAdvance} ?disabled=${!hasNext}>Next <i class="fa-solid fa-arrow-right"></i></button>
      ${checklistTrigger}
    </div>
  `;
}

customElements.define(
  "review-session-controls",
  component(ReviewSessionControls as unknown as () => unknown, { useShadowDOM: false }),
);
