import { html } from "lit-html";
import { component } from "haunted";

// What the reviewer can do with the card in front of them. The card owns the
// edits, so approving and saving carry the patch out in the event and the page
// decides what that means for the session.
//
// Save records corrections to people; approving decides the roster. Adding or removing
// somebody only takes effect on approve, which is why the two are separate buttons.
//
// The host dissolves (`display: contents`) so .review-page__actions stays a
// direct flex item of the header, as review-session-controls does.
const APPROVE_EVENT = "publish";
const SAVE_EVENT = "save";
const REJECT_EVENT = "reject";

// The one thing the labels cannot say. An update and an addition are both claims about the
// world — a human is a source, so adding somebody records a sighting like a scrape would.
// Removing is the exception: it changes who is on the roster, which approving decides.
const SAVE_SCOPE = "Updates and additions are kept. Removing someone takes effect only when you approve.";
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
  canReject: boolean;
  isRejecting: boolean;
  hasSession: boolean;
};

function ReviewSessionActions(host: ReviewSessionActionsHost) {
  const { isReadOnly, dirty, peoplePatch, blockers, canReject, isRejecting, hasSession } = host;

  const blockerTitle = blockers
    .map((b) => `${b.name} — ${b.fieldLabel}: ${b.message}`)
    .join("\n");

  // A clean card publishes what the server already has; only send a patch when
  // the reviewer actually changed something.
  const handleApprove = () =>
    host.dispatchEvent(
      new CustomEvent(APPROVE_EVENT, { detail: { people: dirty ? peoplePatch : null }, bubbles: true, composed: true }),
    );

  const handleSave = () =>
    host.dispatchEvent(
      new CustomEvent(SAVE_EVENT, { detail: { people: peoplePatch }, bubbles: true, composed: true }),
    );

  const handleReject = () =>
    host.dispatchEvent(new CustomEvent(REJECT_EVENT, { bubbles: true, composed: true }));

  const handleEndSession = () =>
    host.dispatchEvent(new CustomEvent(END_SESSION_EVENT, { bubbles: true, composed: true }));

  return html`
    <div class="review-page__actions">
      ${isReadOnly ? "" : html`
      ${dirty ? html`
      <button class="btn-sm review-page__save-btn" @click=${handleSave}>Save updates</button>
      <span class="review-page__actions-rule" title=${SAVE_SCOPE}>${SAVE_SCOPE}</span>
      ` : ""}
      <button
        class="btn-sm review-page__approve-btn btn-gradient"
        @click=${handleApprove}
        ?disabled=${blockers.length > 0}
        title=${blockers.length ? blockerTitle : ""}
      >
        ${blockers.length
          ? `${blockers.length} to fix before approving`
          : dirty
            ? "Save and approve"
            : "Approve"}
      </button>
      ${canReject ? html`
      <button class="btn-sm destructive" @click=${handleReject} ?disabled=${isRejecting}>
        ${isRejecting ? "Rejecting..." : "Reject"}
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
