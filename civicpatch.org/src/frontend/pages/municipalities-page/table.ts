import './table.css';
import { html } from 'lit-html';
import { STATUS_LABELS } from '../../components/progress-dashboard/status-segments.js';
import { dateStringToFriendly } from '../../utils/date-utils.js';
import { jurisdictionOcdidToPath } from '../../components/ocdid-utils.js';
import { Municipality, SortKey, SortDir } from './municipalities-filter.js';

const SORT_HEADERS: { key: SortKey; label: string; class?: string }[] = [
  { key: 'name', label: 'Municipality' },
  { key: 'status', label: 'Status' },
  { key: 'officials', label: 'Officials', class: 'municipalities-table__officials' },
  { key: 'last_verified', label: 'Last verified' },
];

export interface MunicipalitiesTableProps {
  municipalities: Municipality[];
  onClearFilters: () => void;
  sortKey: SortKey;
  sortDir: SortDir;
  onSortChange: (key: SortKey) => void;
}

function renderRow(m: Municipality, jurisdictionHref: string) {
  return html`
    <tr class="municipalities-table__row">
      <td>
        <span
          class="municipalities-table__dot"
          style="background:var(--civ-status-${m.status})"
        ></span>
        <a href="${jurisdictionHref}">${m.name}</a>
      </td>
      <td>
        <span
          class="municipalities-table__status-pill"
          style="background:var(--civ-status-${m.status}); color:var(--civ-bg)"
        >
          ${STATUS_LABELS[m.status] ?? m.status}
        </span>
        ${m.needs_review
          ? html`<span class="municipalities-table__needs-review-badge">Needs review</span>`
          : ''}
      </td>
      <td class="municipalities-table__officials">
        ${m.officials_count > 0 ? m.officials_count : '—'}
      </td>
      <td style=${m.status === 'stale' ? 'color:var(--civ-status-stale)' : ''}>
        ${m.last_verified_at ? dateStringToFriendly(m.last_verified_at) : '—'}
      </td>
      <td>
        <a href="${jurisdictionHref}">View <i class="fa-solid fa-arrow-right"></i></a>
      </td>
    </tr>
  `;
}

function renderSortHeader(
  header: (typeof SORT_HEADERS)[number],
  sortKey: SortKey,
  sortDir: SortDir,
  onSortChange: (key: SortKey) => void,
) {
  const active = sortKey === header.key;
  return html`
    <th class=${header.class ?? ''}>
      <button
        type="button"
        class="municipalities-table__sort-btn${active ? ' municipalities-table__sort-btn--active' : ''}"
        @click=${() => onSortChange(header.key)}
      >
        ${header.label}${active
          ? html`<i class="fa-solid fa-arrow-${sortDir === 'asc' ? 'up' : 'down'}"></i>`
          : ''}
      </button>
    </th>
  `;
}

export function renderMunicipalitiesTable({
  municipalities,
  onClearFilters,
  sortKey,
  sortDir,
  onSortChange,
}: MunicipalitiesTableProps) {
  if (municipalities.length === 0) {
    return html`
      <div class="municipalities-table__empty">
        <p>No municipalities match your search and filters.</p>
        <button type="button" @click=${onClearFilters}>Clear filters</button>
      </div>
    `;
  }

  return html`
    <div class="municipalities-table__wrapper">
      <table class="municipalities-table">
        <thead>
          <tr>
            ${SORT_HEADERS.map((h) => renderSortHeader(h, sortKey, sortDir, onSortChange))}
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          ${municipalities.map((m) =>
            renderRow(m, `/${jurisdictionOcdidToPath(m.jurisdiction_ocdid)}`),
          )}
        </tbody>
      </table>
    </div>
  `;
}
