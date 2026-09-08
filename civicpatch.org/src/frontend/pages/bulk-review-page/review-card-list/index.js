import { html } from "lit-html";
import { component } from "haunted";
import "../../../components/panel/panel.css";
import { Pagination } from "../../../components/pagination/index.js";
import "../../../components/review-card/index.js";

function ReviewCardList({ cards, actionState, loading, error, page, perPage, totalPages, viewMode, onApprove, onReject, onViewChange, onPageChange, onPerPageChange }) {
  if (loading) return html`<div>Loading...</div>`;
  if (error) return html`<div>Error: ${error}</div>`;

  return html`
    <section class="panel">
      <div class="panel__cap">
        <b>awaiting review</b>
        <span class="panel__cap-right">${cards.length} on this page</span>
      </div>
      <div class="bulk-review__view-toggle">
        <button
          class="bulk-review__view-toggle-btn ${viewMode === "quick" ? "bulk-review__view-toggle-btn--active" : ""}"
          @click=${() => onViewChange("quick")}
        >Quick</button>
        <button
          class="bulk-review__view-toggle-btn ${viewMode === "detail" ? "bulk-review__view-toggle-btn--active" : ""}"
          @click=${() => onViewChange("detail")}
        >Detail</button>
      </div>

      <div class="bulk-review__pager-top">
        ${Pagination({ page, totalPages, onPrevious: () => onPageChange(page - 1), onNext: () => onPageChange(page + 1), perPage, onPerPageChange })}
      </div>

      ${cards.length === 0
        ? html`<p>Nothing awaiting review.</p>`
        : html`
          <div class="bulk-review__cards">
            ${cards.map(card => html`
              <review-card
                @approve=${onApprove}
                @reject=${onReject}
                .entry=${card}
                .state=${actionState[card.changeset_id]}
                .viewMode=${viewMode}
              ></review-card>
            `)}
          </div>
        `}

      ${Pagination({ page, totalPages, onPrevious: () => onPageChange(page - 1), onNext: () => onPageChange(page + 1), perPage, onPerPageChange })}
    </section>
  `;
}

customElements.define("bulk-review-card-list", component(ReviewCardList, { useShadowDOM: false }));
