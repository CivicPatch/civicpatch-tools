import { html } from "lit-html";
import { component } from "haunted";
import { useLocalStorage } from "../../hooks/use-local-storage.js";
import { useAuth } from "../../hooks/useAuth.js";
import { usePullRequestActions } from "../../hooks/use-pull-request-actions.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import { useReviewSession } from "./use-review-session.js";
import { landingUrl, STATE_PARAM } from "../review-routes.js";
import { StateKind } from "./review-state.js";
import "./review-session.js";
import "../../components/publish-log/index.js";
import "../review-page/review-page.css";

const DEFAULT_STATE_KEY = "app:default-state";

function getStateFromUrl() {
  return (new URLSearchParams(window.location.search).get(STATE_PARAM) || "").toLowerCase();
}

function ReviewSessionPage() {
  const [defaultState] = useLocalStorage(DEFAULT_STATE_KEY, "");
  const stateCode = (getStateFromUrl() || defaultState || "").toLowerCase();

  const { permissions } = useAuth();
  const { actionState, entries: publishLogEntries, trackMerge, trackClose } = usePullRequestActions();
  const { fsm, advance, back, navigateTo, merge, save, closePr, endSession } = useReviewSession(stateCode, {
    trackMerge,
    trackClose,
  });

  const reviewing = fsm.kind === StateKind.REVIEWING ? fsm : null;
  const currentEntry = reviewing?.current_entry ?? null;
  const session = reviewing?.session ?? null;

  // The card owns the reviewer's edits and hands them over when it asks to
  // publish or save; the page only decides what that does to the session.
  const handleMerge = (e: CustomEvent) => merge(e.detail.people);
  const handleSave = (e: CustomEvent) => save(e.detail.people);
  const handleNavigateTo = (e: CustomEvent) => navigateTo(e.detail.entry_number);

  const prNumber = currentEntry?.pr?.number;
  const isClosingPr = prNumber != null && actionState[prNumber]?.status === PULL_REQUEST_STATUS.LOADING_CLOSE;

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
      .canClosePr=${permissions.PR_CLOSE}
      .isClosingPr=${isClosingPr}
      @back=${back}
      @advance=${advance}
      @navigate-to=${handleNavigateTo}
      @end-session=${endSession}
      @merge=${handleMerge}
      @save=${handleSave}
      @close-pr=${closePr}
    ></review-session>`;
  };

  return html`
    ${renderBody()}
    <civ-publish-log .entries=${publishLogEntries}></civ-publish-log>
  `;
}

customElements.define("review-session-page", component(ReviewSessionPage, { useShadowDOM: false }));
