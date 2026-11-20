import { html } from "lit-html";
import { component, useState } from "haunted";
import { DANGER_VARIANT } from "../../components/confirm-modal/confirm-modal.js";
import { type OfficeEdit } from "../../components/person-editor/office-edits.js";
import { type PersonCard } from "../../components/people/person-cards.js";

// What the reviewer can do with the card in front of them. The card owns the
// edits, so approving and saving carry the patch out in the event and the page
// decides what that means for the session.
//
// Save records corrections to people; approving decides the roster. Adding or removing
// somebody only takes effect on approve, which is why the two are separate buttons.
//
// The host dissolves (`display: contents`) so .review-session__actions stays a
// direct flex item of the header, as review-session-controls does.
const APPROVE_EVENT = "publish";
const SAVE_EVENT = "save";
const REJECT_EVENT = "reject";

// Removing is the exception: it changes who is on the roster, which approving decides.
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
  officeEdits: OfficeEdit[];
  // Who the reviewer took off the roster. Carried because absence no longer means removal:
  // the edit route reads `offices`, and silence about a person leaves them as they are.
  removedIds: string[];
  mergedInto: Map<string, string>;
  // Read by the page's `heldOfficesByPerson`, so an edit to one organization keeps the others.
  cards: PersonCard[];
};

function ReviewSessionActions(host: ReviewSessionActionsHost) {
  const {
    isReadOnly,
    dirty,
    peoplePatch,
    blockers,
    canReject,
    isRejecting,
    hasSession,
    officeEdits,
    removedIds,
    mergedInto,
    cards,
  } = host;

  const blockerTitle = blockers
    .map((b) => `${b.name} — ${b.fieldLabel}: ${b.message}`)
    .join("\n");

  // A clean card publishes what the server already has; only send a patch when
  // the reviewer actually changed something. Office picks ride along either way — they are
  // direct membership writes, not part of `peoplePatch`, so `dirty` (a `peoplePatch` question)
  // has no bearing on whether there are any to apply.
  const handleApprove = () =>
    host.dispatchEvent(
      new CustomEvent(APPROVE_EVENT, {
        detail: { people: dirty ? peoplePatch : null, officeEdits, removedIds, mergedInto, cards },
        bubbles: true,
        composed: true,
      }),
    );

  const handleSave = () =>
    host.dispatchEvent(
      new CustomEvent(SAVE_EVENT, {
        detail: { people: peoplePatch, officeEdits, removedIds, mergedInto, cards },
        bubbles: true,
        composed: true,
      }),
    );

  // Reject sits beside Approve and cannot be undone from here, so it asks first.
  const [confirmingReject, setConfirmingReject] = useState(false);
  const handleReject = () => setConfirmingReject(true);
  const confirmReject = () => {
    setConfirmingReject(false);
    host.dispatchEvent(new CustomEvent(REJECT_EVENT, { bubbles: true, composed: true }));
  };

  const handleEndSession = () =>
    host.dispatchEvent(new CustomEvent(END_SESSION_EVENT, { bubbles: true, composed: true }));

  return html`
    <div class="review-session__actions">
      ${isReadOnly ? "" : html`
      ${dirty ? html`
      <button class="btn-sm review-session__save-btn" @click=${handleSave}>Save updates</button>
      ` : ""}
      <button
        class="btn-sm review-session__approve-btn btn-gradient"
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
      <button class="btn-sm review-session__end-btn" @click=${handleEndSession}>${hasSession ? "End session" : "Exit"}</button>
    </div>
    ${confirmingReject
      ? html`<civ-confirm-modal
          .title=${"Reject this scrape?"}
          .message=${"None of its proposed people will be published. This cannot be undone from here."}
          .confirmLabel=${"Reject scrape"}
          .variant=${DANGER_VARIANT}
          @confirm=${confirmReject}
          @cancel=${() => setConfirmingReject(false)}
        ></civ-confirm-modal>`
      : ""}
  `;
}

customElements.define(
  "review-session-actions",
  component(ReviewSessionActions as unknown as () => unknown, { useShadowDOM: false }),
);
