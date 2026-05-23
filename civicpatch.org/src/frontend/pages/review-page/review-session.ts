import { html } from "lit-html";
import { component, useState } from "haunted";
import "../../components/review-checklist/review-checklist.js";
import "../../components/diff-panel/diff-panel.js";
import "../../components/review-workspace/review-workspace.js";
import "../../components/side-panel/side-panel.js";

interface Progress {
  entryNumber: number;
  hasPrev: boolean;
  resolvedEntryNumbers: Set<number>;
  frontierEntry: number;
  goal: number;
}

type CurrentEntry = {
  request_id: string;
  jurisdiction: { ocdid: string | null; name: string | null; path?: string | null };
  pr: { url: string | null; status: string | null; reviewState: string | null; number?: number | null };
  pr_people: { existing: any[]; proposed: any[] };
  review_data: any;
  source_content_urls: any[];
  is_read_only: boolean;
};

interface ReviewSessionProps {
  progress: Progress;
  hasSession: boolean;
  currentEntry: CurrentEntry | null;
  error: string | null;
  isDirty: boolean;
  currentPeople: any[];
  selectedPeople: any[];
  resolvedMatches: Record<string, any>;
  onMerge: () => void;
  onAdvance: () => void;
  onBack: () => void;
  onNavigateTo: (n: number) => void;
  onEndSession: () => void;
  onClosePr: () => void;
  isClosingPr: boolean;
  onTableDataChange: EventListener;
  onTableReorder: EventListener;
  onPeopleMerge: (...args: any[]) => unknown;
  onBulkDelete: () => void;
  onReset: () => void;
  onAdd: () => void;
}

function ReviewSession({
  progress, hasSession, currentEntry,
  error, isDirty, isClosingPr,
  currentPeople, selectedPeople,
  resolvedMatches,
  onMerge, onAdvance, onBack, onNavigateTo, onEndSession, onClosePr,
  onTableDataChange, onTableReorder, onPeopleMerge, onBulkDelete, onReset, onAdd,
}: ReviewSessionProps) {
  const { entryNumber, hasPrev, resolvedEntryNumbers, frontierEntry, goal } = progress ?? {};
  const { jurisdiction, pr, pr_people, review_data, source_content_urls, is_read_only } = currentEntry ?? {} as Partial<CurrentEntry>;
  const { ocdid: jurisdictionOcdid, name: jurisdictionName } = jurisdiction ?? {};
  const { url: pullRequestUrl, status: pullRequestStatus = null } = pr ?? {};

  const [collapsed, setCollapsed] = useState(false);

  const displayMax = hasSession ? goal : entryNumber;

  function getDotStatus(n) {
    if (n === entryNumber) return "current";
    if (resolvedEntryNumbers.has(n)) return "resolved";
    if (n <= frontierEntry) return "deferred";
    return "future";
  }

  return html`
    <main class="review-page">
      <div class="review-page__sticky-header">
        <div class="review-page__nav">
          <div class="review-page__nav-left">
            <button class="btn-sm review-page__end-btn" @click=${onEndSession}>${hasSession ? "End session" : "Exit"}</button>
          </div>
          ${!hasSession ? html`<div class="review-page__nav-center"></div>` : html`
          <div class="review-page__nav-center">
            <button class="btn-sm review-page__back-btn" @click=${onBack} ?disabled=${!hasPrev}><i class="fa-solid fa-arrow-left"></i> Back</button>
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
            <button class="btn-sm review-page__next-btn" @click=${() => onAdvance()}>Next <i class="fa-solid fa-arrow-right"></i></button>
          </div>
          ${is_read_only ? html`<div class="review-page__nav-right"></div>` : html`
          <div class="review-page__nav-right">
            <button class="btn-sm destructive" @click=${onClosePr} ?disabled=${isClosingPr}>
              ${isClosingPr ? "Closing..." : "Close PR"}
            </button>
            <button class="btn-sm review-page__merge-btn btn-gradient" @click=${onMerge}>
              ${isDirty ? "Save and Publish" : "Publish"}
            </button>
          </div>
          `}
          `}
        </div>
        ${collapsed ? "" : html`
          ${error ? html`<p class="review-page__error">${error}</p>` : ""}
          <div class="review-page__info-row">
            <div class="review-page__pr-meta">
              ${jurisdictionName ? html`<a class="review-page__jurisdiction" href="/${jurisdiction?.path}" target="_blank" rel="noopener">${jurisdictionName}</a>` : ""}
              ${pullRequestUrl ? html`<a class="btn btn-sm" href=${pullRequestUrl} target="_blank" rel="noopener">View PR <i class="fa-solid fa-arrow-up-right-from-square"></i></a>` : ""}
            </div>
            <civ-review-checklist .reviewData=${review_data}></civ-review-checklist>
          </div>
        `}
        <button class="review-page__collapse-btn" @click=${() => setCollapsed(c => !c)} aria-label=${collapsed ? "Show controls" : "Hide controls"}>
          <i class="fa-solid ${collapsed ? "fa-chevron-down" : "fa-chevron-up"}"></i>
        </button>
      </div>
      ${is_read_only ? html`<div class="review-page__status-banner review-page__status-banner--${pullRequestStatus}">${pullRequestStatus}</div>` : ""}
      <civ-diff-panel
        .data=${pr_people ?? { existing: [], proposed: [] }}
      ></civ-diff-panel>
      <div class="review-page__content">
        <civ-review-workspace
          .pullRequest=${currentPeople ?? []}
          .existing=${pr_people?.existing ?? []}
          .selectedPeople=${selectedPeople ?? []}
          .isDirty=${isDirty}
          .isTerminal=${is_read_only}
          .resolvedMatches=${resolvedMatches ?? {}}
          .jurisdictionOcdid=${jurisdictionOcdid}
          .sourceContentUrls=${source_content_urls}
          .onMerge=${onPeopleMerge}
          .onBulkDelete=${onBulkDelete}
          .onReset=${onReset}
          .onAdd=${onAdd}
          @data-change=${onTableDataChange}
          @reorder=${onTableReorder}
        ></civ-review-workspace>
        <civ-side-panel .jurisdictionOcdid=${jurisdictionOcdid} .sourceContentUrls=${source_content_urls}></civ-side-panel>
      </div>
    </main>
  `;
}

customElements.define("review-session", component(ReviewSession, { useShadowDOM: false }));
