import './table.css';
import { html } from 'lit-html';
import { STATUS_LABELS } from '../../components/progress-dashboard/status-segments.js';
import { dateStringToFriendly } from '../../utils/date-utils.js';
import { jurisdictionOcdidToPath } from '../../components/ocdid-utils.js';
import { Municipality } from './municipalities-filter.js';

export interface MunicipalitiesTableProps {
  municipalities: Municipality[];
  onClearFilters: () => void;
}

function renderRow(m: Municipality) {
  return html`
    <tr class="municipalities-table__row">
      <td>
        <span
          class="municipalities-table__dot"
          style="background:var(--civ-status-${m.status})"
        ></span>
        <a href="/${jurisdictionOcdidToPath(m.jurisdiction_ocdid)}">${m.name}</a>
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
        ${m.needs_review
          ? html`<a href="/review">Verify →</a>`
          : html`<a href="/${jurisdictionOcdidToPath(m.jurisdiction_ocdid)}">View →</a>`}
      </td>
    </tr>
  `;
}

export function renderMunicipalitiesTable({ municipalities, onClearFilters }: MunicipalitiesTableProps) {
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
            <th>Municipality</th>
            <th>Status</th>
            <th>Officials</th>
            <th>Last verified</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          ${municipalities.map(renderRow)}
        </tbody>
      </table>
    </div>
  `;
}
