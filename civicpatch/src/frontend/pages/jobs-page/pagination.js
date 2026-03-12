import { html } from 'lit-html';

export const Pagination = ({ page, totalPages, onPrevious, onNext }) =>
  totalPages > 1
    ? html`
        <nav style="display:flex; gap:1rem; align-items:center; margin-top:1.5rem;">
          <button ?disabled=${page <= 1} @click=${onPrevious}>← Previous</button>
          <span>Page ${page} of ${totalPages}</span>
          <button ?disabled=${page >= totalPages} @click=${onNext}>Next →</button>
        </nav>
      `
    : '';