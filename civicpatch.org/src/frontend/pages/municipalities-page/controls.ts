import "./controls.css";
import { html } from "lit-html";
import {
  STATUS_ORDER,
  STATUS_LABELS,
} from "../../components/progress-dashboard/status-segments.js";
import { STATUS_FILTER_ALL } from "./municipalities-filter.js";

export interface ControlsProps {
  query: string;
  onQueryChange: (value: string) => void;
  status: string;
  onStatusChange: (status: string) => void;
  statusPillCounts: Record<string, number>;
  needsReviewOnly: boolean;
  onNeedsReviewToggle: () => void;
  needsReviewCount: number;
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
}: ControlsProps) {
  const pillClass = (active: boolean) =>
    `municipalities-controls__pill${active ? " municipalities-controls__pill--active" : ""}`;

  return html`
    <div class="municipalities-controls">
      <input
        type="search"
        class="municipalities-controls__search"
        placeholder="Search municipalities…"
        .value=${query}
        @input=${(e: Event) =>
          onQueryChange((e.target as HTMLInputElement).value)}
      />

      <div class="municipalities-controls__row">
        <div class="municipalities-controls__pills">
          <button
            type="button"
            class=${pillClass(status === STATUS_FILTER_ALL)}
            @click=${() => onStatusChange(STATUS_FILTER_ALL)}
          >
            All
            <span class="municipalities-controls__pill-count"
              >${statusPillCounts.all ?? 0}</span
            >
          </button>
          ${STATUS_ORDER.map(
            (key) => html`
              <button
                type="button"
                class=${pillClass(status === key)}
                @click=${() => onStatusChange(key)}
              >
                <span
                  class="municipalities-controls__pill-dot"
                  style="background:var(--civ-status-${key})"
                ></span>
                ${STATUS_LABELS[key]}
                <span class="municipalities-controls__pill-count"
                  >${statusPillCounts[key] ?? 0}</span
                >
              </button>
            `,
          )}
        </div>

        <label class="municipalities-controls__checkbox">
          <input
            type="checkbox"
            .checked=${needsReviewOnly}
            @change=${onNeedsReviewToggle}
          />
          Needs review
          <span class="municipalities-controls__pill-count"
            >${needsReviewCount}</span
          >
        </label>
      </div>
    </div>
  `;
}
