import { html } from "lit-html";
import { component } from "haunted";
import { accessibleLabel } from "./sidebar-model.js";

// Opens the checklist drawer. Named specifically rather than "open" because it
// bubbles up through review-session-controls to the page — a generic name on a
// shared path is asking to be caught by the wrong listener.
const CHECKLIST_OPEN_EVENT = "checklist-open";

type ReviewSidebarTriggerHost = HTMLElement & {
  done: number;
  total: number;
};

function ReviewSidebarTrigger(host: ReviewSidebarTriggerHost) {
  const { done, total } = host;

  const handleOpen = () =>
    host.dispatchEvent(new CustomEvent(CHECKLIST_OPEN_EVENT, { bubbles: true, composed: true }));

  // The visible label stays a substring of the accessible name (WCAG 2.5.3),
  // which adds the state — "2/5" alone tells a screen reader nothing.
  return html`
    <button
      class="btn btn-sm secondary review-sidebar__trigger"
      @click=${handleOpen}
      aria-label=${accessibleLabel(done, total)}
    >
      <i class="fa-solid fa-list-check"></i> Checklist
      <span class="review-sidebar__trigger-count">${done}/${total}</span>
    </button>
  `;
}

customElements.define(
  "review-sidebar-trigger",
  component(ReviewSidebarTrigger as unknown as () => unknown, { useShadowDOM: false }),
);
