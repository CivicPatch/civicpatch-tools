import { html } from "lit-html";
import "../../components/panel/panel.css";
import "./coverage-by-state.css";
import "../../components/verify-cta/verify-cta.ts";
import { stateNameForCode } from "../../components/ocdid-utils.js";
import { sortedRows, type DashboardState } from "./coverage-by-state-model.js";

export function renderCoverageByState({
  statesData,
  onSelectState,
  selectedState,
  isLoggedIn,
  toReviewCount,
  hasActiveSession,
}: {
  statesData: Record<string, DashboardState>;
  onSelectState: (stateCode: string) => void;
  selectedState: string;
  isLoggedIn: boolean;
  toReviewCount: number;
  hasActiveSession: boolean;
}) {
  const rows = sortedRows(statesData);
  if (rows.length === 0) return "";

  return html`
    <div class="panel coverage-by-state">
      <div class="panel__cap">
        <b>coverage by state</b>
        <span class="coverage-by-state__legend">
          <span class="coverage-by-state__swatch coverage-by-state__swatch--fresh"></span>fresh
          <span class="coverage-by-state__swatch coverage-by-state__swatch--stale"></span>stale
        </span>
      </div>
      <div class="coverage-by-state__list">
        ${rows.map(
          (row) => html`
            <button
              type="button"
              class="coverage-by-state__row"
              @click=${() => onSelectState(row.code)}
            >
              <span class="coverage-by-state__name"
                >${stateNameForCode(row.code)}</span
              >
              <span class="coverage-by-state__bar">
                <i
                  class="coverage-by-state__segment coverage-by-state__segment--fresh"
                  style="width:${(row.fresh / row.known) * 100}%"
                ></i>
                <i
                  class="coverage-by-state__segment coverage-by-state__segment--stale"
                  style="width:${(row.stale / row.known) * 100}%"
                ></i>
              </span>
              <span class="coverage-by-state__count"
                >${row.needsReview} needs review</span
              >
            </button>
          `,
        )}
      </div>
      <civ-verify-cta
        .isLoggedIn=${isLoggedIn}
        .toReviewCount=${toReviewCount}
        .state=${selectedState}
        .hasActiveSession=${hasActiveSession}
      ></civ-verify-cta>
    </div>
  `;
}
