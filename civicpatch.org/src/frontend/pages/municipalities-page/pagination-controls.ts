import './pagination-controls.css';
import { html } from 'lit-html';
import { PageResult, computePageWindow } from './pagination.js';

export interface PaginationControlsProps {
  page: number;
  pageInfo: PageResult<unknown>;
  onPageChange: (page: number) => void;
}

export function renderPaginationControls({ page, pageInfo, onPageChange }: PaginationControlsProps) {
  const { start, end, total, totalPages } = pageInfo;
  if (totalPages <= 1) return html``;

  return html`
    <div class="municipalities-pagination">
      <span class="municipalities-pagination__summary">${start}–${end} of ${total}</span>
      <div class="municipalities-pagination__pages">
        <button
          type="button"
          ?disabled=${page <= 1}
          @click=${() => onPageChange(page - 1)}
        >
          Prev
        </button>
        ${computePageWindow(page, totalPages).map((item) =>
          item === 'ellipsis'
            ? html`<span class="municipalities-pagination__ellipsis">…</span>`
            : html`
                <button
                  type="button"
                  class="municipalities-pagination__page${item === page
                    ? ' municipalities-pagination__page--active'
                    : ''}"
                  @click=${() => onPageChange(item)}
                >
                  ${item}
                </button>
              `,
        )}
        <button
          type="button"
          ?disabled=${page >= totalPages}
          @click=${() => onPageChange(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  `;
}
