import { component, useState } from "haunted";
import { html } from "lit-html";
import { createRef, ref } from "lit-html/directives/ref.js";
import { jurisdictionOcdidToFriendly } from "../ocdid-utils.js";
import { PULL_REQUEST_STATUS } from "../pull-request-status.js";
import { pullRequestUrlToNumber } from "../pr-utils.js";
import { fetchReview, fetchPullRequestData } from "../../../api.js";
import "../../../components/badge/badge.js";
import "../../../components/review-panel/review-panel.js";

export function stateColor(state) {
  switch (state) {
    case "open":
      return "open";
    case "closed":
      return "closed";
    case "merged":
      return "merged";
    default:
      return "draft";
  }
}

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

const REVIEW_STATE = {
  "changes_requested": {
    label: "Issues",
    variant: "danger",
  },
  "approved": {
    label: "Approved",
    variant: "success",
  },
}

const PullRequestCardHeader = ({ pr, state, stats }) => {
  const [reviewData, setReviewData] = useState(null);
  const [fullData, setFullData] = useState(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const pullRequestNumber = pullRequestUrlToNumber(pr?.pull_request_url);
  const popoverRef = createRef();

  async function handleIssuesClick() {
    const el = popoverRef.value;
    if (!reviewData && !reviewLoading) {
      setReviewLoading(true);
      try {
        const [review, prData] = await Promise.all([
          fetchReview(pr.request_id),
          fetchPullRequestData(pr.jurisdiction_ocdid, pr.request_id),
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
        detail: { pullRequestNumber },
        bubbles: true,
      }),
    );
  };

  const handleClose = (el) => {
    el.currentTarget.dispatchEvent(
      new CustomEvent("onClose", {
        detail: { pullRequestNumber },
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
    let buttonName = "Merge";
    if (state?.status === PULL_REQUEST_STATUS.LOADING_MERGE) buttonName = "Merging...";
    else if (state?.status === PULL_REQUEST_STATUS.MERGED) buttonName = "Merged";
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
      <civ-badge
        .label=${pr?.jurisdiction_name || jurisdictionOcdidToFriendly(pr?.jurisdiction_ocdid)}
      ></civ-badge>
      <a class="pr-card__link" href=${pr?.pull_request_url} target="_blank" rel="noopener">
        #${pullRequestNumber || "—"}
      </a>
      <span
        class="pr-card__state pr-card__state--${stateColor(pr?.pull_request_status)}"
      >
        ${pr?.pull_request_status || "unknown"}
      </span>
      <a
        class="pr-card__link"
        href="/jurisdictions?jurisdiction_ocdid=${pr?.jurisdiction_ocdid}"
        target="_blank"
        rel="noopener"
      >
        Detail
      </a>
    </div>
    <div class="header-item-center">
      ${pr?.pull_request_review_state ? html`
        <button class="btn-ghost" @click=${handleIssuesClick} ?disabled=${reviewLoading}>
          <civ-badge
            .label=${reviewLoading ? "Loading..." : (REVIEW_STATE[pr.pull_request_review_state]?.label ?? pr.pull_request_review_state)}
            .variant=${REVIEW_STATE[pr.pull_request_review_state]?.variant ?? "primary"}
          ></civ-badge>
        </button>
        <div popover ${ref(popoverRef)} class="review-popover">
          <civ-review-panel
            .reviewData=${reviewData}
            .existing=${fullData?.existing ?? []}
            .pullRequest=${fullData?.pull_request ?? []}
          ></civ-review-panel>
        </div>
      ` : ""}
      ${renderStats(stats ?? {})}
    </div>
    <div class="header-item-right">
      ${renderCloseButton()} ${renderMergeButton()}
    </div>
  </div>`;
};


customElements.define(
  "pull-request-card-header",
  component(PullRequestCardHeader, { useShadowDOM: false }),
);
