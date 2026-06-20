import { html } from "lit-html";
import { component } from "haunted";
import "../../components/review-checklist/review-checklist.js";
import "../../components/diff-panel/diff-panel.js";
import "../../components/review-workspace/review-workspace.js";
import "../../components/side-panel/side-panel.js";
import { type Progress } from "./review-session-controls.js";
import "./review-session-controls.js";
import { ReviewMode, type ReviewModeValue } from "./review-state.js";

type CurrentEntry = {
  request_id: string;
  jurisdiction: { ocdid: string | null; name: string | null; path?: string | null };
  pr: { url: string | null; status: string | null; reviewState: string | null; number?: number | null };
  mode: ReviewModeValue;
  pr_people: { existing: any[]; proposed: any[] };
  review_data: any;
  source_content_urls: any[];
  is_read_only: boolean;
  has_next: boolean;
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
  canClosePr: boolean;
  isClosingPr: boolean;
  onTableDataChange: EventListener;
  onTableReorder: EventListener;
  onPeopleMerge: (...args: any[]) => unknown;
  onBulkDelete: () => void;
  onReset: () => void;
  onAdd: () => void;
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
}

function ReviewSession({
  progress, hasSession, currentEntry,
  error, isDirty, isClosingPr, canClosePr,
  currentPeople, selectedPeople,
  resolvedMatches,
  onMerge, onAdvance, onBack, onNavigateTo, onEndSession, onClosePr,
  onTableDataChange, onTableReorder, onPeopleMerge, onBulkDelete, onReset, onAdd, onPersonSave,
}: ReviewSessionProps) {
  const { jurisdiction, pr, mode, pr_people, review_data, source_content_urls, is_read_only, has_next } = currentEntry ?? {} as Partial<CurrentEntry>;
  const { ocdid: jurisdictionOcdid, name: jurisdictionName } = jurisdiction ?? {};
  const { url: pullRequestUrl, status: pullRequestStatus = null } = pr ?? {};
  const isBaseline = mode === ReviewMode.BASELINE;

  return html`
    <main class="review-page">
      <review-session-controls
        .progress=${progress}
        .hasSession=${hasSession}
        .hasNext=${has_next}
        .isReadOnly=${is_read_only}
        .canClosePr=${canClosePr}
        .isClosingPr=${isClosingPr}
        .isDirty=${isDirty}
        .onEndSession=${onEndSession}
        .onBack=${onBack}
        .onNavigateTo=${onNavigateTo}
        .onAdvance=${onAdvance}
        .onClosePr=${onClosePr}
        .onMerge=${onMerge}
      ></review-session-controls>
      ${error ? html`<p class="review-page__error">${error}</p>` : ""}
      <div class="review-page__info-row">
        <div class="review-page__pr-meta">
          ${jurisdictionName ? html`<a class="review-page__jurisdiction" href="/${jurisdiction?.path}" target="_blank" rel="noopener">${jurisdictionName}</a>` : ""}
          ${pullRequestUrl ? html`<a class="btn btn-sm" href=${pullRequestUrl} target="_blank" rel="noopener">View PR <i class="fa-solid fa-arrow-up-right-from-square"></i></a>` : ""}
        </div>
        <civ-review-checklist .reviewData=${review_data}></civ-review-checklist>
      </div>
      ${is_read_only ? html`<div class="review-page__status-banner review-page__status-banner--${pullRequestStatus}">${pullRequestStatus}</div>` : ""}
      ${isBaseline
        ? html`<div class="review-page__baseline-banner">First capture for ${jurisdictionName ?? "this jurisdiction"} — nothing to compare against yet. Publishing creates these records for the first time.</div>`
        : html`<civ-diff-panel
            .data=${pr_people ?? { existing: [], proposed: [] }}
          ></civ-diff-panel>`}
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
          .onPersonSave=${onPersonSave}
          @data-change=${onTableDataChange}
          @reorder=${onTableReorder}
        ></civ-review-workspace>
        <civ-side-panel .sourceContentUrls=${source_content_urls}></civ-side-panel>
      </div>
    </main>
  `;
}

customElements.define("review-session", component(ReviewSession, { useShadowDOM: false }));
