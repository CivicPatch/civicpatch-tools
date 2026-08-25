import { html } from "lit-html";
import { component } from "haunted";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { STORAGE_KEYS } from "../../utils/storage-keys.js";
import { useAuth } from "../../hooks/useAuth.js";
import { useReviewActions } from "../../hooks/use-review-actions.js";
import { REVIEW_ACTION } from "../../components/pull-request-card/review-action.js";
import { useReviewSession } from "./use-review-session.js";
import { landingUrl, STATE_PARAM } from "../review-routes.js";
import { StateKind } from "./review-state.js";
import "./review-session.js";
import "../../components/publish-log/index.js";
import "../review-page/review-page.css";

function getStateFromUrl() {
  return (new URLSearchParams(window.location.search).get(STATE_PARAM) || "").toLowerCase();
}

function ReviewSessionPage() {
  const [defaultState] = useLocalStorage(STORAGE_KEYS.DEFAULT_STATE, "", { ttl: PERSIST_FOREVER });
  const stateCode = (getStateFromUrl() || defaultState || "").toLowerCase();

  const { permissions } = useAuth();
  const { actionState, entries: publishLogEntries, trackApprove, trackReject } = useReviewActions();
  const { fsm, advance, back, navigateTo, merge, save, rejectScrape, endSession } = useReviewSession(stateCode, {
    trackApprove,
    trackReject,
  });

  const reviewing = fsm.kind === StateKind.REVIEWING ? fsm : null;
  const currentEntry = reviewing?.current_entry ?? null;
  const session = reviewing?.session ?? null;

  // The card owns the reviewer's edits and hands them over when it asks to
  // publish or save; the page only decides what that does to the session.
  const handlePublish = (e: CustomEvent) => merge(e.detail.people);
  const handleSave = (e: CustomEvent) => save(e.detail.people);
  const handleNavigateTo = (e: CustomEvent) => navigateTo(e.detail.entry_number);

  const requestId = currentEntry?.request_id;
  const isRejecting = requestId != null && actionState[requestId]?.status === REVIEW_ACTION.REJECTING;

  const progress = reviewing
    ? {
        entryNumber: reviewing.entry_number,
        hasPrev: reviewing.entry_number > 1,
        resolvedEntryNumbers: reviewing.resolved_entry_numbers,
        savedEntryNumbers: reviewing.saved_entry_numbers,
        failedEntryNumbers: new Set(reviewing.failed_entries.keys()),
        frontierEntry: reviewing.frontier_entry,
        total: reviewing.total,
      }
    : null;

  // The publish error for the entry we're currently on (if its last publish was
  // rejected), shown as an in-place banner so the reviewer can fix and retry.
  const publishError = reviewing ? reviewing.failed_entries.get(reviewing.entry_number) ?? null : null;

  const renderBody = () => {
    if (fsm.kind === StateKind.LOADING) {
      return html`<main class="review-page"><p>Loading...</p></main>`;
    }
    if (fsm.kind === StateKind.ERROR) {
      return html`<main class="review-page">
        <p class="review-page__error">${fsm.message}</p>
        <a class="btn btn-sm" href=${landingUrl(stateCode)}>Back to review</a>
      </main>`;
    }
    return html`<review-session
      .currentEntry=${currentEntry}
      .hasSession=${session != null}
      .progress=${progress}
      .error=${publishError}
      .canReject=${permissions.can_reject_scrape}
      .isRejecting=${isRejecting}
      @back=${back}
      @advance=${advance}
      @navigate-to=${handleNavigateTo}
      @end-session=${endSession}
      @publish=${handlePublish}
      @save=${handleSave}
      @reject=${rejectScrape}
    ></review-session>`;
  };

  return html`
    ${renderBody()}
    <civ-publish-log .entries=${publishLogEntries}></civ-publish-log>
  `;
}

customElements.define("review-session-page", component(ReviewSessionPage, { useShadowDOM: false }));
