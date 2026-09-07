import "./pagination.css";
import { html } from 'lit-html';

const PER_PAGE_OPTIONS = [10, 25, 50];

// The per-page selector is opt-in: pass `onPerPageChange` to get it, omit it when the caller
// renders its own control.
export const Pagination = ({ page, totalPages, onPrevious, onNext, perPage = null, onPerPageChange = null }) => {
  return html`
    <div class="civ-pagination">
      <button
        class="btn btn-sm civ-pagination__btn"
        ?disabled=${page <= 1}
        @click=${onPrevious}
      ><i class="fa-solid fa-arrow-left"></i> Back</button>
      <span class="civ-pagination__counter">Page ${page} of ${totalPages}</span>
      <button
        class="btn btn-sm civ-pagination__btn"
        ?disabled=${page >= totalPages}
        @click=${onNext}
      >Next <i class="fa-solid fa-arrow-right"></i></button>
      ${onPerPageChange ? html`
        <div class="civ-pagination__per-page">
          <label>Per page
            <select @change=${onPerPageChange}>
              ${PER_PAGE_OPTIONS.map(n => html`<option value=${n} ?selected=${n === perPage}>${n}</option>`)}
            </select>
          </label>
        </div>
      ` : null}
    </div>
  `;
};
