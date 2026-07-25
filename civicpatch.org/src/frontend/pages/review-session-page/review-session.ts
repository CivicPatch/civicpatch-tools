import { html } from "lit-html";
import { component, useEffect, useState } from "haunted";
import "../../components/review-checklist/review-checklist.js";
import "../../components/people-diff/people-diff.js";
import "../../components/source-content/source-content-debug-modal.js";
import { type Progress } from "./review-session-controls.js";
import "./review-session-controls.js";
import "./report-issue-modal.js";
import { ReviewMode, type ReviewModeValue } from "./review-state.js";
import { fetchReportedIssues, reportReviewIssue } from "../../api.js";

type ReportedIssue = {
  id: string;
  github_issue_url: string | null;
  github_issue_number: number | null;
  status: string;
};

type CurrentEntry = {
  request_id: string;
  jurisdiction: { ocdid: string | null; name: string | null; path?: string | null; website_url?: string | null };
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
  onAdd: () => void;
  onResetPerson: (id: string) => void;
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
}

function ReviewSession({
  progress, hasSession, currentEntry,
  error, isDirty, isClosingPr, canClosePr,
  currentPeople,
  onMerge, onAdvance, onBack, onNavigateTo, onEndSession, onClosePr,
  onAdd, onResetPerson, onPersonSave,
}: ReviewSessionProps) {
  const { jurisdiction, pr, mode, pr_people, review_data, source_content_urls, is_read_only, has_next } = currentEntry ?? {} as Partial<CurrentEntry>;
  const { ocdid: jurisdictionOcdid, name: jurisdictionName, website_url: jurisdictionWebsiteUrl } = jurisdiction ?? {};
  const { url: pullRequestUrl, status: pullRequestStatus = null } = pr ?? {};
  const isBaseline = mode === ReviewMode.BASELINE;

  const [showReportModal, setShowReportModal] = useState(false);
  const [isReportingIssue, setIsReportingIssue] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [reportedIssues, setReportedIssues] = useState<ReportedIssue[]>([]);
  const [debugOpen, setDebugOpen] = useState(false);
  const hasSourceContent = Boolean(source_content_urls && source_content_urls.length > 0);

  const requestId = currentEntry?.request_id ?? null;

  useEffect(() => {
    if (!requestId) {
      setReportedIssues([]);
      return;
    }
    fetchReportedIssues(requestId)
      .then((result: { data: ReportedIssue[] }) => setReportedIssues(result.data))
      .catch(() => setReportedIssues([]));
  }, [requestId]);

  const handleReportIssueOpen = () => {
    setReportError(null);
    setShowReportModal(true);
  };

  const handleReportIssueClose = () => {
    if (isReportingIssue) return;
    setShowReportModal(false);
  };

  const handleReportIssueConfirmed = async (ev: CustomEvent) => {
    const { description } = ev.detail as { description: string };
    if (!currentEntry || isReportingIssue) return;
    setIsReportingIssue(true);
    setReportError(null);
    try {
      const result = await reportReviewIssue(currentEntry.request_id, description);
      setReportedIssues((prev) => [
        {
          id: result.data.id,
          github_issue_url: result.data.github_issue_url,
          github_issue_number: result.data.github_issue_number,
          status: "pending",
        },
        ...prev,
      ]);
      setShowReportModal(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setReportError(`Failed to file issue: ${message}`);
    } finally {
      setIsReportingIssue(false);
    }
  };

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
          ${jurisdictionName
            ? html`<a class="review-page__jurisdiction" href="/${jurisdiction?.path}" target="_blank" rel="noopener">
                ${jurisdictionName} <i class="fa-solid fa-arrow-up-right-from-square"></i>
              </a>`
            : ""}
          ${jurisdictionWebsiteUrl
            ? html`<a class="review-page__jurisdiction-website" href=${jurisdictionWebsiteUrl} target="_blank" rel="noopener">
                ${jurisdictionWebsiteUrl} <i class="fa-solid fa-arrow-up-right-from-square"></i>
              </a>`
            : ""}
          ${pullRequestUrl ? html`<a class="btn btn-sm" href=${pullRequestUrl} target="_blank" rel="noopener">View PR <i class="fa-solid fa-arrow-up-right-from-square"></i></a>` : ""}
          ${hasSourceContent ? html`<button class="btn btn-sm secondary" @click=${() => setDebugOpen(true)}>Debug</button>` : ""}
          <button class="btn btn-sm secondary" @click=${handleReportIssueOpen}>Report issue</button>
          ${reportedIssues.length
            ? html`
                <ul class="review-page__reported-issues">
                  ${reportedIssues.map(
                    (issue) => html`
                      <li>
                        <a href=${issue.github_issue_url ?? "#"} target="_blank" rel="noopener">Issue #${issue.github_issue_number}</a>
                        — ${issue.status}
                      </li>
                    `,
                  )}
                </ul>
              `
            : ""}
        </div>
        <civ-review-checklist .reviewData=${review_data}></civ-review-checklist>
      </div>
      ${is_read_only ? html`<div class="review-page__status-banner review-page__status-banner--${pullRequestStatus}">${pullRequestStatus}</div>` : ""}
      ${isBaseline
        ? html`<div class="review-page__baseline-banner">First capture for ${jurisdictionName ?? "this jurisdiction"} — nothing to compare against yet. Publishing creates these records for the first time.</div>`
        : ""}
      <people-diff
        .existing=${pr_people?.existing ?? []}
        .currentPeople=${currentPeople ?? []}
        .issues=${review_data?.issues ?? []}
        .onPersonSave=${onPersonSave}
        .onAdd=${onAdd}
        .onResetPerson=${onResetPerson}
        .jurisdictionOcdid=${jurisdictionOcdid}
        .isReadOnly=${is_read_only}
      ></people-diff>
      ${showReportModal
        ? html`
            <report-issue-modal
              .submitting=${isReportingIssue}
              .error=${reportError}
              @modal-close=${handleReportIssueClose}
              @report-issue-confirmed=${handleReportIssueConfirmed}
            ></report-issue-modal>
          `
        : null}
      ${debugOpen
        ? html`
            <source-content-debug-modal
              .sourceContentUrls=${source_content_urls}
              @modal-close=${() => setDebugOpen(false)}
            ></source-content-debug-modal>
          `
        : null}
    </main>
  `;
}

customElements.define("review-session", component(ReviewSession, { useShadowDOM: false }));
