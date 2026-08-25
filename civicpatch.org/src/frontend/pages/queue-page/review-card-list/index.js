import { html } from "lit-html";
import { component } from "haunted";
import { Pagination } from "../../../components/pagination/index.js";
import "../../../components/review-card/index.js";

function ReviewCardList({ cards, actionState, loading, error, page, perPage, totalPages, viewMode, onMerge, onClose, onViewChange, onPageChange, onPerPageChange }) {
  if (loading) return html`<div>Loading...</div>`;
  if (error) return html`<div>Error: ${error}</div>`;

  return html`
    <section>
      <div class="queue-page__section-label">Awaiting review</div>
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

      <div style="margin-bottom: 1rem;">
        ${Pagination({ page, totalPages, onPrevious: () => onPageChange(page - 1), onNext: () => onPageChange(page + 1), perPage, onPerPageChange })}
      </div>

      ${cards.length === 0
        ? html`<p>Nothing awaiting review.</p>`
        : html`
          <div style="display: flex; gap: 2rem; flex-direction: column;">
            ${cards.map(card => html`
              <review-card
                @onMerge=${onMerge}
                @onClose=${onClose}
                .entry=${card}
                .state=${actionState[card.request_id]}
                .viewMode=${viewMode}
              ></review-card>
            `)}
          </div>
        `}

      ${Pagination({ page, totalPages, onPrevious: () => onPageChange(page - 1), onNext: () => onPageChange(page + 1), perPage, onPerPageChange })}
    </section>
  `;
}

customElements.define("queue-review-card-list", component(ReviewCardList, { useShadowDOM: false }));
