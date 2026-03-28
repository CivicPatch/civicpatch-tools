import { html } from "lit-html";
import { component } from "haunted";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import "../../components/review-checklist/review-checklist.js";
import "../../components/diff-panel/diff-panel.js";
import "../../components/review-workspace/review-workspace.js";
import "./source-content.js";

function ReviewSession({
  goal, entryNumber, hasNext, hasPrev,
  prState, error, isDirty, pullRequestUrl, jurisdictionName, reviewState,
  currentPeople, tableData, selectedPeople, reviewData, sourceContentUrls,
  passedEntryNumbers, resolvedEntryNumbers, frontierEntry,
  onMerge, onUpdateBranch, onAdvance, onBack, onPass, onNavigateTo, onPause,
  onTableDataChange, onTableReorder, onPeopleMerge, onBulkDelete, onReset,
}) {
  const isTerminal = prState?.status === PULL_REQUEST_STATUS.MERGED;
  const isMerging = prState?.status === PULL_REQUEST_STATUS.LOADING_MERGE;
  const isUpdatingBranch = prState?.status === PULL_REQUEST_STATUS.LOADING_UPDATE_BRANCH;
  const isBranchOutOfDate = prState?.status === PULL_REQUEST_STATUS.BRANCH_OUT_OF_DATE;
  const displayMax = hasNext ? goal : entryNumber;

  function getDotStatus(n) {
    if (n === entryNumber) return "current";
    if (resolvedEntryNumbers.has(n)) return "resolved";
    if (passedEntryNumbers.has(n)) return "passed";
    if (n <= frontierEntry) return "deferred";
    return "future";
  }

  return html`
    <main class="review-page">
      <div class="review-page__nav">
        <button class="btn-sm review-page__back-btn" @click=${onBack} ?disabled=${!hasPrev}>← Back</button>
        <span class="review-page__progress">${entryNumber} of ${displayMax}</span>
        <div class="review-page__dots">
          ${Array.from({ length: goal }, (_, i) => i + 1).map((n) => {
            const status = getDotStatus(n);
            return html`<button
              class="review-page__dot review-page__dot--${status}"
              ?disabled=${status === "future" || status === "current"}
              @click=${() => onNavigateTo(n)}
            ></button>`;
          })}
        </div>
        <button class="btn-sm review-page__pass-btn" @click=${onPass} ?disabled=${!hasNext}>Pass</button>
        <button class="btn-sm" @click=${() => onAdvance()} ?disabled=${!hasNext || entryNumber >= goal}>Next →</button>
        ${isBranchOutOfDate
          ? html`<button class="btn-sm" @click=${onUpdateBranch} ?disabled=${isUpdatingBranch}>
              ${isUpdatingBranch ? "Updating…" : "Update Branch"}
            </button>`
          : html`<button class="btn-sm" @click=${onMerge} ?disabled=${isTerminal || isMerging}>
              ${isMerging ? "Merging…" : prState?.status === PULL_REQUEST_STATUS.MERGED ? "Merged" : isDirty ? "Save and Merge" : "Merge"}
            </button>`}
      </div>
      ${error ? html`<p class="review-page__error">${error}</p>` : ""}
      ${prState?.status === PULL_REQUEST_STATUS.ERROR ? html`<p class="review-page__error">${prState.error}</p>` : ""}
      ${isBranchOutOfDate ? html`<p class="review-page__error">Branch is out of date — update it, then merge.</p>` : ""}
      <div class="review-page__info-row">
        <div class="review-page__pr-meta">
          ${jurisdictionName ? html`<span class="review-page__jurisdiction">${jurisdictionName}</span>` : ""}
          ${reviewState ? html`<span class="review-page__review-state review-page__review-state--${reviewState}">${reviewState === "changes_requested" ? "Changes requested" : "Approved"}</span>` : ""}
          ${pullRequestUrl ? html`<a class="btn btn-sm" href=${pullRequestUrl} target="_blank" rel="noopener">View PR ↗</a>` : ""}
        </div>
        <civ-review-checklist .reviewData=${reviewData}></civ-review-checklist>
      </div>
      <civ-diff-panel
        .data=${{ existing: currentPeople?.existing ?? [], pull_request: currentPeople?.pull_request ?? [] }}
      ></civ-diff-panel>
      <div class="review-page__content">
        <civ-review-workspace
          .pullRequest=${tableData ?? []}
          .existing=${currentPeople?.existing ?? []}
          .selectedPeople=${selectedPeople ?? []}
          .isDirty=${isDirty}
          .onMerge=${onPeopleMerge}
          .onBulkDelete=${onBulkDelete}
          .onReset=${onReset}
          @data-change=${onTableDataChange}
          @reorder=${onTableReorder}
        ></civ-review-workspace>
        <source-content .sourceContentUrls=${sourceContentUrls}></source-content>
      </div>
      <button class="review-page__end-btn" @click=${onPause}>End session</button>
    </main>
  `;
}

customElements.define("review-session", component(ReviewSession, { useShadowDOM: false }));
