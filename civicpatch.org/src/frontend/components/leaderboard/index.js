import "./leaderboard.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchLeaderboard } from "../../api.js";

export const LEADERBOARD_PERIOD_WEEK = "week";
export const LEADERBOARD_PERIOD_ALL_TIME = "all_time";

const FALLBACK_ICONS = [
  "fa-mug-hot",
  "fa-mug-saucer",
  "fa-martini-glass",
  "fa-wine-glass",
  "fa-beer-mug-empty",
  "fa-bottle-water",
  "fa-lemon",
  "fa-cookie",
  "fa-ice-cream",
  "fa-apple-whole",
  "fa-candy-cane",
  "fa-carrot",
];

function hashIcon(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (Math.imul(31, h) + name.charCodeAt(i)) | 0;
  return FALLBACK_ICONS[Math.abs(h) % FALLBACK_ICONS.length];
}

function Leaderboard({ title, period = LEADERBOARD_PERIOD_ALL_TIME }) {
  const [entries, setEntries] = useState(null);
  const [brokenAvatars, setBrokenAvatars] = useState(new Set());
  useEffect(() => {
    setEntries(null);
    fetchLeaderboard(period)
      .then((res) => setEntries(res.data.entries))
      .catch(() => setEntries([]));
  }, [period]);
  const handleAvatarError = (id) => {
    setBrokenAvatars((prev) => new Set([...prev, id]));
  };
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
        ${entries.map((entry, i) => {
          const avatarBroken = brokenAvatars.has(entry.provider_user_id);
          const showAvatar = entry.provider === "github" && !avatarBroken;
          return html`
            <div class="leaderboard__row">
              <span class="leaderboard__rank">${i + 1}</span>
              <span class="leaderboard__identity">
                ${showAvatar ? html`
                  <img
                    class="leaderboard__avatar"
                    src="https://avatars.githubusercontent.com/u/${entry.provider_user_id}?s=32"
                    alt=""
                    width="24"
                    height="24"
                    @error=${() => handleAvatarError(entry.provider_user_id)}
                  />
                ` : html`
                  <i class="leaderboard__avatar-fallback fa-solid ${hashIcon(entry.display_name)}"></i>
                `}
                <span class="leaderboard__contributor">
                  ${entry.provider === "github"
                    ? html`<a href="https://github.com/${entry.display_name}" target="_blank" rel="noopener noreferrer">${entry.display_name}</a>`
                    : entry.display_name}
                </span>
              </span>
              <span class="leaderboard__count">${entry.resolved_count} reviews</span>
            </div>
          `;
        })}
      </div>
    </div>
  `;
}

customElements.define("civ-leaderboard", component(Leaderboard, { useShadowDOM: false }));
