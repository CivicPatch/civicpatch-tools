import { html } from "lit-html";
import { component } from "haunted";
import { Pagination } from "../../../components/pagination/index.js";
import "../../../components/pull-request-card/index.js";

const PER_PAGE_OPTIONS = [10, 25, 50];

function PrList({ pullRequests, pullRequestState, loading, error, page, perPage, totalPages, viewMode, onMerge, onClose, onViewChange, onPageChange, onPerPageChange }) {
  if (loading) return html`<div>Loading...</div>`;
  if (error) return html`<div>Error: ${error}</div>`;

  const pagination = Pagination({
    page,
    totalPages,
    onPrevious: () => onPageChange(page - 1),
    onNext: () => onPageChange(page + 1),
    onGoToPage: onPageChange,
  });

  return html`
    <section>
      <div class="queue-page__top-controls">
        <div class="queue-page__view-toggle">
          <button
            class="queue-page__view-toggle-btn ${viewMode === "quick" ? "queue-page__view-toggle-btn--active" : ""}"
            @click=${() => onViewChange("quick")}
          >Quick</button>
          <button
            class="queue-page__view-toggle-btn ${viewMode === "detail" ? "queue-page__view-toggle-btn--active" : ""}"
            @click=${() => onViewChange("detail")}
          >Detail</button>
        </div>
        <div class="queue-page__pagination queue-page__pagination--top">
          ${pagination}
        </div>
        <div class="queue-page__per-page">
          <label>Per page
            <select @change=${onPerPageChange}>
              ${PER_PAGE_OPTIONS.map(n => html`<option value=${n} ?selected=${n === perPage}>${n}</option>`)}
            </select>
          </label>
        </div>
      </div>

      ${pullRequests.length === 0
        ? html`<p>No pull requests found.</p>`
        : html`
          <div style="display: flex; gap: 2rem; flex-direction: column;">
            ${pullRequests.map(pr => html`
              <pr-card
                @onMerge=${onMerge}
                @onClose=${onClose}
                .entry=${pr}
                .state=${pullRequestState[pr.pr.number]}
                .viewMode=${viewMode}
              ></pr-card>
            `)}
          </div>
        `}

      <div class="queue-page__pagination">${pagination}</div>
    </section>
  `;
}

customElements.define("queue-pr-list", component(PrList, { useShadowDOM: false }));
