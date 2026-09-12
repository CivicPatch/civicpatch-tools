import { html } from "lit-html";
import { component } from "haunted";
import { ref } from "lit/directives/ref.js";
import "../../../components/panel/panel.css";
import { Pagination } from "../../../components/pagination/index.js";
import "../../../components/review-card/index.js";
import { usePagerRef } from "../../../hooks/use-pager-ref.ts";

function ReviewCardList({ cards, actionState, loading, error, page, perPage, totalPages, viewMode, onApprove, onReject, onViewChange, onPageChange, onPerPageChange }) {
  const { listRef, scrollToTop } = usePagerRef();

  if (loading) return html`<div>Loading...</div>`;
  if (error) return html`<div>Error: ${error}</div>`;

  // Built once so Next/Previous re-orients to the top of the section either way — clicking
  // the bottom pager most often leaves the reader below what just changed above them.
  const pager = Pagination({
    page,
    totalPages,
    onPrevious: () => {
      onPageChange(page - 1);
      scrollToTop();
    },
    onNext: () => {
      onPageChange(page + 1);
      scrollToTop();
    },
    perPage,
    onPerPageChange,
  });

  return html`
    <section class="panel" ${ref(listRef)}>
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
        ${pager}
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

      ${pager}
    </section>
  `;
}

customElements.define("bulk-review-card-list", component(ReviewCardList, { useShadowDOM: false }));
