import { component, useState } from "haunted";
import { html, nothing } from "lit-html";
import { createRef, ref } from "lit-html/directives/ref.js";
import { jurisdictionOcdidToFriendly } from "../ocdid-utils.js";
import { REVIEW_ACTION } from "./review-action.js";

// The parent listens with `@approve` / `@reject`, which lit-html parses, so the listener side
// stays literal.
const APPROVE_EVENT = "approve";
const REJECT_EVENT = "reject";
import { fetchReview, fetchPullRequestData } from "../../api.js";
import "../badge/badge.js";
import "../review-panel/review-panel.js";
import { jurisdictionOcdidToPath } from "../ocdid-utils.js";

const renderStats = ({ added, removed, changed }) => {
  if (!added && !removed && !changed) return "";
  return html`
    <span class="review-card__stats">
      ${added ? html`<span class="review-card__stat review-card__stat--added">+${added}</span>` : ""}
      ${removed ? html`<span class="review-card__stat review-card__stat--removed">−${removed}</span>` : ""}
      ${changed ? html`<span class="review-card__stat review-card__stat--changed">~${changed}</span>` : ""}
    </span>
  `;
};

const PullRequestCardHeader = ({ entry, state, stats, createdAt }) => {
  const [reviewData, setReviewData] = useState(null);
  const [fullData, setFullData] = useState(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const popoverRef = createRef();

  async function handleIssuesClick() {
    const el = popoverRef.value;
    if (!reviewData && !reviewLoading) {
      setReviewLoading(true);
      try {
        const [review, prData] = await Promise.all([
          fetchReview(entry.changeset_id),
          fetchPullRequestData(entry.jurisdiction.ocdid, entry.changeset_id),
        ]);
        setReviewData(review?.data ?? null);
        setFullData({ existing: prData?.existing ?? [], pull_request: prData?.data ?? [] });
      } finally {
        setReviewLoading(false);
      }
    }
    el?.showPopover();
  }

  const handleApprove = (el) => {
    el.currentTarget.dispatchEvent(
      new CustomEvent(APPROVE_EVENT, {
        detail: { changeset_id: entry.changeset_id, jurisdiction_ocdid: entry.jurisdiction.ocdid },
        bubbles: true,
      }),
    );
  };

  const handleReject = (el) => {
    el.currentTarget.dispatchEvent(
      new CustomEvent(REJECT_EVENT, {
        detail: { changeset_id: entry.changeset_id },
        bubbles: true,
      }),
    );
  };

  const isTerminal =
    state?.status === REVIEW_ACTION.APPROVED ||
    state?.status === REVIEW_ACTION.REJECTED ||
    state?.status === REVIEW_ACTION.ERROR;

  const isLoading = state?.status === REVIEW_ACTION.APPROVING || state?.status === REVIEW_ACTION.REJECTING;

  const renderMergeButton = () => {
    let buttonName = "Publish";
    if (state?.status === REVIEW_ACTION.APPROVING) buttonName = "Publishing...";
    else if (state?.status === REVIEW_ACTION.APPROVED) buttonName = "Published";
    else if (state?.status === REVIEW_ACTION.ERROR) buttonName = "Error";

    return html`<button
      class="btn-sm"
      @click=${handleApprove}
      ?disabled=${isTerminal || isLoading}
    >${buttonName}</button>`;
  };

  const renderCloseButton = () => {
    let buttonName = "Close";
    if (state?.status === REVIEW_ACTION.REJECTING) buttonName = "Closing...";
    else if (state?.status === REVIEW_ACTION.REJECTED) buttonName = "Closed";
    else if (state?.status === REVIEW_ACTION.ERROR) buttonName = "Error";

    return html`<button
      class="destructive btn-sm"
      @click=${handleReject}
      ?disabled=${isTerminal || isLoading}
    >${buttonName}</button>`;
  }

  return html` <div class="review-card__header">
    <div class="header-item-left">
      <a class="review-card__jurisdiction-link" href="/${jurisdictionOcdidToPath(entry?.jurisdiction?.path)}" target="_blank" rel="noopener">
        ${entry?.jurisdiction?.name || jurisdictionOcdidToFriendly(entry?.jurisdiction?.ocdid)}
      </a>
      ${entry?.pr?.url ? html`
      <a class="review-card__link" href=${entry.pr.url} target="_blank" rel="noopener">published data</a>
      ` : nothing}
    </div>
    <div class="header-item-center">
      <button class="btn-ghost" @click=${handleIssuesClick} ?disabled=${reviewLoading}>
        <civ-badge
          .label=${reviewLoading ? "Loading..." : (entry?.issue_count > 0 ? `${entry.issue_count} issue${entry.issue_count !== 1 ? 's' : ''}` : "Approved")}
          .variant=${entry?.issue_count > 0 ? "danger" : "success"}
        ></civ-badge>
      </button>
      <div popover ${ref(popoverRef)} class="review-popover">
        <civ-review-panel
          .reviewData=${reviewData}
          .existing=${fullData?.existing ?? []}
          .pullRequest=${fullData?.pull_request ?? []}
        ></civ-review-panel>
      </div>
      ${renderStats(stats ?? {})}
    </div>
    <div class="header-item-right">
      <!-- data-visual-volatile: the visual suite masks this. Seeded PRs are created
           at seed time, so the rendered date is whatever day the run happens on and
           the baseline would go stale overnight for no code reason. -->
      ${createdAt ? html`<span class="review-card__meta" data-visual-volatile>${new Date(createdAt).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}</span>` : ""}
      ${renderCloseButton()} ${renderMergeButton()}
    </div>
  </div>`;
};


customElements.define(
  "review-card-header",
  component(PullRequestCardHeader, { useShadowDOM: false }),
);
