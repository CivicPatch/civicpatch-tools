import { html } from 'lit-html';

function getPageRange(page, totalPages) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const delta = 2;
  const pages = new Set([1, totalPages]);
  for (let i = page - delta; i <= page + delta; i++) {
    if (i >= 1 && i <= totalPages) pages.add(i);
  }
  const sorted = Array.from(pages).sort((a, b) => a - b);
  const result = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] === 2) result.push(sorted[i - 1] + 1);
    else if (i > 0 && sorted[i] - sorted[i - 1] > 2) result.push("...");
    result.push(sorted[i]);
  }
  return result;
}

export const Pagination = ({ page, totalPages, onPrevious, onNext, onGoToPage, hrefForPage = () => '#' }) => {
  if (totalPages <= 1) return html``;
  return html`
    <a
      class="btn btn-sm civ-pagination__prev-btn"
      href=${hrefForPage(page - 1)}
      aria-disabled=${page <= 1}
      @click=${(e) => { e.preventDefault(); if (page > 1) onPrevious(); }}
    ><i class="fa-solid fa-arrow-left"></i> Back</a>
    <nav class="civ-pagination__page-numbers">
      ${getPageRange(page, totalPages).map((n) =>
        n === "..."
          ? html`<span class="civ-pagination__page-ellipsis">…</span>`
          : html`<a
              class="btn btn-sm civ-pagination__page-btn${n === page ? " civ-pagination__page-btn--active" : ""}"
              href=${hrefForPage(n)}
              @click=${(e) => { e.preventDefault(); onGoToPage(n); }}
            >${n}</a>`
      )}
    </nav>
    <a
      class="btn btn-sm civ-pagination__next-btn"
      href=${hrefForPage(page + 1)}
      aria-disabled=${page >= totalPages}
      @click=${(e) => { e.preventDefault(); if (page < totalPages) onNext(); }}
    >Next <i class="fa-solid fa-arrow-right"></i></a>
  `;
};
