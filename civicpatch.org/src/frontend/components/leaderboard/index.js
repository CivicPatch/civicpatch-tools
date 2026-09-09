import "./leaderboard.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchLeaderboard } from "../../api.js";

export const LEADERBOARD_PERIOD_WEEK = "week";
export const LEADERBOARD_PERIOD_ALL_TIME = "all_time";

function Leaderboard({ title, period = LEADERBOARD_PERIOD_ALL_TIME }) {
  const [entries, setEntries] = useState(null);
  useEffect(() => {
    setEntries(null);
    fetchLeaderboard(period)
      .then((res) => setEntries(res.data.entries))
      .catch(() => setEntries([]));
  }, [period]);
  const header = html`
    <div class="leaderboard__header">
      <div class="panel__cap"><b>${title}</b></div>
    </div>
  `;
  if (entries === null) {
    return html`<div class="leaderboard">${header}</div>`;
  }
  if (entries.length === 0) {
    return html`
      <div class="leaderboard">
        ${header}
        <div class="leaderboard__empty">No contributor data yet.</div>
      </div>
    `;
  }
  return html`
    <div class="leaderboard">
      ${header}
      <div class="leaderboard__grid">
        ${entries.map((entry, i) => html`
          <div class="leaderboard__row">
            <span class="leaderboard__rank">${i + 1}</span>
            <span class="leaderboard__contributor">
              ${entry.provider === "github"
                ? html`<a href="https://github.com/${entry.display_name}" target="_blank" rel="noopener noreferrer">${entry.display_name}</a>`
                : entry.display_name}
            </span>
            <span class="leaderboard__count">${entry.resolved_count} reviews</span>
          </div>
        `)}
      </div>
    </div>
  `;
}

customElements.define("civ-leaderboard", component(Leaderboard, { useShadowDOM: false }));
