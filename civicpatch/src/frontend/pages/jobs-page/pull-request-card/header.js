import { component } from "haunted";
import { html } from "lit-html";
import { jurisdictionOcdidToFriendly } from "../ocdid-utils.js";
import { PULL_REQUEST_STATUS } from "../index.js";

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

const PullRequestCardHeader = ({ pr, state }) => {
  const handleMerge = (el) => {
    el.currentTarget.dispatchEvent(
      new CustomEvent("onMerge", {
        detail: {
          pullRequestNumber: pr.pull_request_number,
        },
        bubbles: true,
      }),
    );
  };
  const renderMergeButton = () => {
    let buttonName = "Merge";
    let disabled = false;
    switch (state?.status) {
      case PULL_REQUEST_STATUS.LOADING:
        buttonName = "Merging...";
        disabled = true;
        break;
      case PULL_REQUEST_STATUS.MERGED:
        buttonName = "Merged";
        disabled = true;
        break;
      case PULL_REQUEST_STATUS.ERROR:
        buttonName = "Error";
        disabled = true;
        break;
      default:
        break;
    }

    return html`<div class="header-item-right">
      <button
        class="pr-card__merge-button"
        @click=${handleMerge}
        ?disabled=${disabled}
      >
        ${buttonName}
      </button>
    </div>`;
  };

  return html` <div class="pr-card__header">
    <div class="header-item-left">
      <span class="pr-card__jurisdiction">
        ${jurisdictionOcdidToFriendly(pr?.jurisdiction_ocdid)}
      </span>
      ${pr?.github_title
        ? html`<span class="pr-card__title">${pr.github_title}</span>`
        : ""}
      <a class="pr-card__link" href=${pr?.url} target="_blank" rel="noopener">
        #${pr?.pull_request_number || "—"}
      </a>
      <span
        class="pr-card__state pr-card__state--${stateColor(pr?.github_state)}"
      >
        ${pr?.github_state || "unknown"}
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
    ${renderMergeButton()}
  </div>`;
};

customElements.define(
  "pull-request-card-header",
  component(PullRequestCardHeader, { useShadowDOM: false }),
);
