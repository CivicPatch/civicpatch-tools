import { html } from "lit-html";
import { component } from "haunted";
import { useLocalStorage } from "../../hooks/use-local-storage.js";
import { usePullRequestActions } from "../../hooks/use-pull-request-actions.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import { useReviewSession } from "./use-review-session.js";
import { useReviewPeople } from "./use-review-people.js";
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

  const { actionState, entries: publishLogEntries, trackMerge, trackClose } = usePullRequestActions();
  const { fsm, advance, back, navigateTo, merge, closePr, endSession } = useReviewSession(stateCode, {
    trackMerge,
    trackClose,
  });

  const reviewing = fsm.kind === StateKind.REVIEWING ? fsm : null;
  const currentEntry = reviewing?.current_entry ?? null;
  const session = reviewing?.session ?? null;

  const {
    currentPeople,
    dirty,
    peopleToSubmit,
    selectedPeople,
    resolvedMatches,
    handleAdd,
    handleLinkPerson,
    handleTableDataChange,
    handleTableDataReorder,
    handleBulkDelete,
    handleMerge: handlePeopleMerge,
    handleResetAll,
  } = useReviewPeople(currentEntry);

  const handleMerge = () => merge(dirty ? peopleToSubmit : null);

  const prNumber = currentEntry?.pr?.number;
  const isClosingPr = prNumber != null && actionState[prNumber]?.status === PULL_REQUEST_STATUS.LOADING_CLOSE;

  const progress = reviewing
    ? {
        entryNumber: reviewing.entry_number,
        hasPrev: reviewing.entry_number > 1,
        resolvedEntryNumbers: reviewing.resolved_entry_numbers,
        frontierEntry: reviewing.frontier_entry,
        total: reviewing.total,
      }
    : null;

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
      .error=${null}
      .isDirty=${dirty}
      .currentPeople=${currentPeople}
      .selectedPeople=${selectedPeople}
      .onMerge=${handleMerge}
      .onClosePr=${closePr}
      .isClosingPr=${isClosingPr}
      .onAdvance=${advance}
      .onBack=${back}
      .onNavigateTo=${navigateTo}
      .onEndSession=${endSession}
      .onTableDataChange=${handleTableDataChange}
      .onTableReorder=${handleTableDataReorder}
      .onPeopleMerge=${handlePeopleMerge}
      .onBulkDelete=${handleBulkDelete}
      .onReset=${handleResetAll}
      .onAdd=${handleAdd}
      @link-person=${handleLinkPerson}
      .resolvedMatches=${resolvedMatches}
    ></review-session>`;
  };

  return html`
    ${renderBody()}
    <civ-publish-log .entries=${publishLogEntries}></civ-publish-log>
  `;
}

customElements.define("review-session-page", component(ReviewSessionPage, { useShadowDOM: false }));
