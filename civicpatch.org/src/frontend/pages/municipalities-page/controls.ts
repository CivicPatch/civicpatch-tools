import './controls.css';
import { html } from 'lit-html';
import { STATUS_ORDER, STATUS_LABELS } from '../../components/progress-dashboard/status-segments.js';
import { STATUS_FILTER_ALL, SortKey, SortDir } from './municipalities-filter.js';

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'name', label: 'Name' },
  { key: 'status', label: 'Status' },
  { key: 'officials', label: 'Officials' },
  { key: 'last_verified', label: 'Last verified' },
];

export interface ControlsProps {
  query: string;
  onQueryChange: (value: string) => void;
  status: string;
  onStatusChange: (status: string) => void;
  statusPillCounts: Record<string, number>;
  needsReviewOnly: boolean;
  onNeedsReviewToggle: () => void;
  needsReviewCount: number;
  sortKey: SortKey;
  sortDir: SortDir;
  onSortChange: (key: SortKey) => void;
}

export function renderControls({
  query,
  onQueryChange,
  status,
  onStatusChange,
  statusPillCounts,
  needsReviewOnly,
  onNeedsReviewToggle,
  needsReviewCount,
  sortKey,
  sortDir,
  onSortChange,
}: ControlsProps) {
  const pillClass = (active: boolean) =>
    `municipalities-controls__pill${active ? ' municipalities-controls__pill--active' : ''}`;

  return html`
    <div class="municipalities-controls">
      <input
        type="search"
        class="municipalities-controls__search"
        placeholder="Search municipalities…"
        .value=${query}
        @input=${(e: Event) => onQueryChange((e.target as HTMLInputElement).value)}
      />

      <div class="municipalities-controls__pills">
        <button
          type="button"
          class=${pillClass(status === STATUS_FILTER_ALL)}
          @click=${() => onStatusChange(STATUS_FILTER_ALL)}
        >
          All <span class="municipalities-controls__pill-count">${statusPillCounts.all ?? 0}</span>
        </button>
        ${STATUS_ORDER.map(
          (key) => html`
            <button type="button" class=${pillClass(status === key)} @click=${() => onStatusChange(key)}>
              <span
                class="municipalities-controls__pill-dot"
                style="background:var(--civ-status-${key})"
              ></span>
              ${STATUS_LABELS[key]}
              <span class="municipalities-controls__pill-count">${statusPillCounts[key] ?? 0}</span>
            </button>
          `,
        )}
        <button
          type="button"
          class=${pillClass(needsReviewOnly)}
          @click=${onNeedsReviewToggle}
        >
          Needs review only
          <span class="municipalities-controls__pill-count">${needsReviewCount}</span>
        </button>
      </div>

      <div class="municipalities-controls__sort">
        ${SORT_OPTIONS.map(
          (opt) => html`
            <button
              type="button"
              class="municipalities-controls__sort-btn${sortKey === opt.key
                ? ' municipalities-controls__sort-btn--active'
                : ''}"
              @click=${() => onSortChange(opt.key)}
            >
              ${opt.label}${sortKey === opt.key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
            </button>
          `,
        )}
      </div>
    </div>
  `;
}
