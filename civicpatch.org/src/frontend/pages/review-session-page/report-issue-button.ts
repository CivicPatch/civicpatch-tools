import { html } from "lit-html";
import { component, useEffect, useState } from "haunted";
import "./report-issue-modal.js";
import { fetchReportedIssues, reportReviewIssue } from "../../api.js";

// Reporting a data problem is self-contained: the button, the issues already
// filed against this card, and the modal that files a new one. It owns that
// state so the review card doesn't have to — the card only says which entry is
// under review.
type ReportedIssue = {
  id: string;
  github_issue_url: string | null;
  github_issue_number: number | null;
  status: string;
};

const PENDING_STATUS = "pending";

type ReportIssueButtonHost = HTMLElement & {
  changesetId: string | null;
};

function ReportIssueButton(host: ReportIssueButtonHost) {
  const { changesetId } = host;

  const [showModal, setShowModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [reportedIssues, setReportedIssues] = useState<ReportedIssue[]>([]);

  useEffect(() => {
    if (!changesetId) {
      setReportedIssues([]);
      return;
    }
    fetchReportedIssues(changesetId)
      .then((result: { data: ReportedIssue[] }) => setReportedIssues(result.data))
      .catch(() => setReportedIssues([]));
  }, [changesetId]);

  const handleOpen = () => {
    setSubmitError(null);
    setShowModal(true);
  };

  const handleClose = () => {
    if (isSubmitting) return;
    setShowModal(false);
  };

  const handleConfirmed = async (ev: CustomEvent) => {
    const { description } = ev.detail as { description: string };
    if (!changesetId || isSubmitting) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const result = await reportReviewIssue(changesetId, description);
      setReportedIssues((prev) => [
        {
          id: result.data.id,
          github_issue_url: result.data.github_issue_url,
          github_issue_number: result.data.github_issue_number,
          status: PENDING_STATUS,
        },
        ...prev,
      ]);
      setShowModal(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setSubmitError(`Failed to file issue: ${message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return html`
    <button class="btn btn-sm secondary" @click=${handleOpen}>Report issue</button>
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
    ${showModal
      ? html`
          <report-issue-modal
            .submitting=${isSubmitting}
            .error=${submitError}
            @modal-close=${handleClose}
            @report-issue-confirmed=${handleConfirmed}
          ></report-issue-modal>
        `
      : null}
  `;
}

customElements.define(
  "report-issue-button",
  component(ReportIssueButton as unknown as () => unknown, { useShadowDOM: false }),
);
