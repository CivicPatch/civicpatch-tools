import { html } from "lit-html";
import { component } from "haunted";

// What the reviewer can do with the card in front of them. The card owns the
// edits, so publishing and saving carry the patch out in the event and the page
// decides what that means for the session.
//
// The host dissolves (`display: contents`) so .review-page__actions stays a
// direct flex item of the header, as review-session-controls does.
const PUBLISH_EVENT = "publish";
const SAVE_EVENT = "save";
const CLOSE_PR_EVENT = "close-pr";
const END_SESSION_EVENT = "end-session";

export interface Blocker {
  name: string;
  fieldLabel: string;
  message: string;
}

type ReviewSessionActionsHost = HTMLElement & {
  isReadOnly: boolean;
  dirty: boolean;
  peoplePatch: unknown;
  blockers: Blocker[];
  canClosePr: boolean;
  isClosingPr: boolean;
  hasSession: boolean;
};

function ReviewSessionActions(host: ReviewSessionActionsHost) {
  const { isReadOnly, dirty, peoplePatch, blockers, canClosePr, isClosingPr, hasSession } = host;

  const blockerTitle = blockers
    .map((b) => `${b.name} — ${b.fieldLabel}: ${b.message}`)
    .join("\n");

  // A clean card publishes what the server already has; only send a patch when
  // the reviewer actually changed something.
  const handlePublish = () =>
    host.dispatchEvent(
      new CustomEvent(PUBLISH_EVENT, { detail: { people: dirty ? peoplePatch : null }, bubbles: true, composed: true }),
    );

  const handleSave = () =>
    host.dispatchEvent(
      new CustomEvent(SAVE_EVENT, { detail: { people: peoplePatch }, bubbles: true, composed: true }),
    );

  const handleClosePr = () =>
    host.dispatchEvent(new CustomEvent(CLOSE_PR_EVENT, { bubbles: true, composed: true }));

  const handleEndSession = () =>
    host.dispatchEvent(new CustomEvent(END_SESSION_EVENT, { bubbles: true, composed: true }));

  return html`
    <div class="review-page__actions">
      ${isReadOnly ? "" : html`
      ${dirty ? html`
      <button class="btn-sm review-page__save-btn" @click=${handleSave}>Save for later</button>
      ` : ""}
      <button
        class="btn-sm review-page__publish-btn btn-gradient"
        @click=${handlePublish}
        ?disabled=${blockers.length > 0}
        title=${blockers.length ? blockerTitle : ""}
      >
        ${blockers.length
          ? `${blockers.length} to fix before publishing`
          : dirty
            ? "Save and Publish"
            : "Publish"}
      </button>
      ${canClosePr ? html`
      <button class="btn-sm destructive" @click=${handleClosePr} ?disabled=${isClosingPr}>
        ${isClosingPr ? "Closing..." : "Close PR"}
      </button>
      ` : ""}
      `}
      <button class="btn-sm review-page__end-btn" @click=${handleEndSession}>${hasSession ? "End session" : "Exit"}</button>
    </div>
  `;
}

customElements.define(
  "review-session-actions",
  component(ReviewSessionActions as unknown as () => unknown, { useShadowDOM: false }),
);
