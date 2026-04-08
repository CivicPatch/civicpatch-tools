import { component, useState } from "haunted";
import { html } from "lit-html";
import { createRef, ref } from "lit-html/directives/ref.js";
import { jurisdictionOcdidToFriendly } from "../ocdid-utils.js";
import { PULL_REQUEST_STATUS } from "./pull-request-status.js";
import { fetchReview, fetchPullRequestData } from "../../api.js";
import "../badge/badge.js";
import "../review-panel/review-panel.js";

const renderStats = ({ added, removed, changed }) => {
  if (!added && !removed && !changed) return "";
  return html`
    <span class="pr-card__stats">
      ${added ? html`<span class="pr-card__stat pr-card__stat--added">+${added}</span>` : ""}
      ${removed ? html`<span class="pr-card__stat pr-card__stat--removed">−${removed}</span>` : ""}
      ${changed ? html`<span class="pr-card__stat pr-card__stat--changed">~${changed}</span>` : ""}
    </span>
  `;
};

const PullRequestCardHeader = ({ entry, state, stats, createdAt }) => {
  const [reviewData, setReviewData] = useState(null);
  const [fullData, setFullData] = useState(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const pullRequestNumber = entry?.pr?.number;
  const popoverRef = createRef();

  async function handleIssuesClick() {
    const el = popoverRef.value;
    if (!reviewData && !reviewLoading) {
      setReviewLoading(true);
      try {
        const [review, prData] = await Promise.all([
          fetchReview(entry.request_id),
          fetchPullRequestData(entry.jurisdiction.ocdid, entry.request_id),
        ]);
        setReviewData(review?.data ?? null);
        setFullData({ existing: prData?.existing ?? [], pull_request: prData?.data ?? [] });
      } finally {
        setReviewLoading(false);
      }
    }
    el?.showPopover();
  }

  const handleMerge = (el) => {
    el.currentTarget.dispatchEvent(
      new CustomEvent("onMerge", {
        detail: { request_id: entry.request_id, pullRequestNumber, jurisdiction_ocdid: entry.jurisdiction.ocdid },
        bubbles: true,
      }),
    );
  };

  const handleClose = (el) => {
    el.currentTarget.dispatchEvent(
      new CustomEvent("onClose", {
        detail: { request_id: entry.request_id, pullRequestNumber },
        bubbles: true,
      }),
    );
  };

  const isTerminal =
    state?.status === PULL_REQUEST_STATUS.MERGED ||
    state?.status === PULL_REQUEST_STATUS.CLOSED ||
    state?.status === PULL_REQUEST_STATUS.ERROR;

  const isLoading = state?.status === PULL_REQUEST_STATUS.LOADING_MERGE || state?.status === PULL_REQUEST_STATUS.LOADING_CLOSE;

  const renderMergeButton = () => {
    let buttonName = "Publish";
    if (state?.status === PULL_REQUEST_STATUS.LOADING_MERGE) buttonName = "Publishing...";
    else if (state?.status === PULL_REQUEST_STATUS.MERGED) buttonName = "Published";
    else if (state?.status === PULL_REQUEST_STATUS.ERROR) buttonName = "Error";

    return html`<button
      class="btn-sm"
      @click=${handleMerge}
      ?disabled=${isTerminal || isLoading}
    >${buttonName}</button>`;
  };

  const renderCloseButton = () => {
    let buttonName = "Close";
    if (state?.status === PULL_REQUEST_STATUS.LOADING_CLOSE) buttonName = "Closing...";
    else if (state?.status === PULL_REQUEST_STATUS.CLOSED) buttonName = "Closed";
    else if (state?.status === PULL_REQUEST_STATUS.ERROR) buttonName = "Error";

    return html`<button
      class="destructive btn-sm"
      @click=${handleClose}
      ?disabled=${isTerminal || isLoading}
    >${buttonName}</button>`;
  }

  return html` <div class="pr-card__header">
    <div class="header-item-left">
      <a class="pr-card__jurisdiction-link" href="/jurisdictions?jurisdiction_ocdid=${entry?.jurisdiction?.ocdid}" target="_blank" rel="noopener">
        ${entry?.jurisdiction?.name || jurisdictionOcdidToFriendly(entry?.jurisdiction?.ocdid)}
      </a>
      <a class="pr-card__link" href=${entry?.pr?.url} target="_blank" rel="noopener">
        #${pullRequestNumber || "—"}
      </a>
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
      ${createdAt ? html`<span class="pr-card__meta">${new Date(createdAt).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}</span>` : ""}
      ${renderCloseButton()} ${renderMergeButton()}
    </div>
  </div>`;
};


customElements.define(
  "pull-request-card-header",
  component(PullRequestCardHeader, { useShadowDOM: false }),
);
