import { html } from "lit-html";
import { component } from "haunted";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import "../../components/review-checklist/review-checklist.js";
import "../../components/diff-panel/diff-panel.js";
import "../../components/review-workspace/review-workspace.js";
import "../../components/side-panel/side-panel.js";

function ReviewSession({
  progress, jurisdiction, pr,
  mergeState, error, isDirty,
  prPeople, currentPeople, selectedPeople, reviewData, sourceContentUrls,
  resolvedMatches,
  onMerge, onAdvance, onBack, onPass, onNavigateTo, onPause,
  onTableDataChange, onTableReorder, onPeopleMerge, onBulkDelete, onReset, onAdd,
}) {
  const { entryNumber, hasNext, hasPrev, passedEntryNumbers, resolvedEntryNumbers, frontierEntry, goal } = progress ?? {};
  const { ocdid: jurisdictionOcdid, name: jurisdictionName } = jurisdiction ?? {};
  const { url: pullRequestUrl, status: pullRequestStatus, reviewState } = pr ?? {};

  const isTerminal = mergeState?.status === PULL_REQUEST_STATUS.MERGED;
  const isMerging = mergeState?.status === PULL_REQUEST_STATUS.LOADING_MERGE;
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
      <div class="review-page__sticky-header">
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
          <button class="btn-sm" @click=${onMerge} ?disabled=${isTerminal || isMerging}>
            ${isMerging ? "Merging…" : isTerminal ? "Merged" : isDirty ? "Save and Merge" : "Merge"}
          </button>
        </div>
        ${error ? html`<p class="review-page__error">${error}</p>` : ""}
        ${mergeState?.status === PULL_REQUEST_STATUS.ERROR ? html`<p class="review-page__error">${mergeState.error}</p>` : ""}
        <div class="review-page__info-row">
          <div class="review-page__pr-meta">
            ${jurisdictionName ? html`<a class="review-page__jurisdiction" href="/jurisdictions?jurisdiction_ocdid=${jurisdictionOcdid}" target="_blank" rel="noopener">${jurisdictionName} ↗</a>` : ""}
            ${pullRequestUrl ? html`<a class="btn btn-sm" href=${pullRequestUrl} target="_blank" rel="noopener">View PR ↗</a>` : ""}
          </div>
          <civ-review-checklist .reviewData=${reviewData}></civ-review-checklist>
        </div>
      </div>
      <civ-diff-panel
        .data=${prPeople ?? { existing: [], proposed: [] }}
      ></civ-diff-panel>
      <div class="review-page__content">
        <civ-review-workspace
          .pullRequest=${currentPeople ?? []}
          .existing=${prPeople?.existing ?? []}
          .selectedPeople=${selectedPeople ?? []}
          .isDirty=${isDirty}
          .resolvedMatches=${resolvedMatches ?? {}}
          .jurisdictionOcdid=${jurisdictionOcdid}
          .onMerge=${onPeopleMerge}
          .onBulkDelete=${onBulkDelete}
          .onReset=${onReset}
          .onAdd=${onAdd}
          @data-change=${onTableDataChange}
          @reorder=${onTableReorder}
        ></civ-review-workspace>
        <civ-side-panel .jurisdictionOcdid=${jurisdictionOcdid} .sourceContentUrls=${sourceContentUrls}></civ-side-panel>
      </div>
      <button class="review-page__end-btn" @click=${onPause}>End session</button>
    </main>
  `;
}

customElements.define("review-session", component(ReviewSession, { useShadowDOM: false }));
