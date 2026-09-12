import { html } from "lit-html";
import "../../components/panel/panel.css";
import "./recent-activity.css";
import {
  jurisdictionOcdidToPath,
  jurisdictionOcdidToState,
} from "../../components/ocdid-utils.js";
import type { RecentActivityEntry } from "./use-recent-activity.ts";

const MINUTE_MS = 60 * 1000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;
const RELATIVE_TIME_CUTOFF_MS = 7 * DAY_MS;

// Past a week a relative count stops being intuitive, so it falls back to a real date —
// same threshold GitHub/Twitter use. Compact form (no "ago") matches this app's own
// durationBetween() convention (date-utils.js), not a generic library format.
function formatDate(iso: string) {
  const date = new Date(iso);
  const elapsed = Date.now() - date.getTime();
  if (elapsed >= RELATIVE_TIME_CUTOFF_MS) {
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  if (elapsed < HOUR_MS) return `${Math.max(1, Math.floor(elapsed / MINUTE_MS))}m`;
  if (elapsed < DAY_MS) return `${Math.floor(elapsed / HOUR_MS)}h`;
  return `${Math.floor(elapsed / DAY_MS)}d`;
}

// Color-codes by outcome, not by type name, so a glance at the list tells
// removals from edits from taxonomy changes without reading every summary.
const ERROR_TYPES = new Set(["dismiss_review", "delete_person", "delete_post", "delete_role"]);
const CHG_TYPES = new Set([
  "edit_person",
  "edit_jurisdiction",
  "edit_post",
  "edit_role",
  "assign_membership",
  "assert_field",
]);
const NOTE_TYPES = new Set(["add_role", "reorder_roles"]);

export function roleForType(type: string): "main" | "error" | "chg" | "note" {
  if (ERROR_TYPES.has(type)) return "error";
  if (CHG_TYPES.has(type)) return "chg";
  if (NOTE_TYPES.has(type)) return "note";
  return "main";
}

// Whoever did it always shows, matching /activity's own convention — /~{username} is a
// moderation view (see routers/frontend.py's comment on that route), so only the link to it is
// admin-gated, not the name itself.
export function authorDisplayMode(
  isSystem: boolean,
  canViewProfiles: boolean,
): "link" | "text" | "none" {
  if (isSystem) return "none";
  return canViewProfiles ? "link" : "text";
}

// `previouslySeen: null` means the reader hasn't loaded the list yet — nothing on a first load
// is "fresh," there being nothing prior to be new against. Lives here, not in
// use-recent-activity.ts, so it can be unit-tested without pulling in haunted.
export function markFreshEntries<T extends { id: string }>(
  fetched: T[],
  previouslySeen: Set<string> | null,
): (T & { isFresh: boolean })[] {
  return fetched.map((entry) => ({
    ...entry,
    isFresh: previouslySeen !== null && !previouslySeen.has(entry.id),
  }));
}

// Logged-in only. Renders entry.summary as-is (core/activity.py::summarize_activity
// already computed it), so there's no verb mapping to duplicate here.
export function renderRecentActivity({
  entries,
  canViewProfiles,
}: {
  entries: RecentActivityEntry[];
  canViewProfiles: boolean;
}) {
  if (entries.length === 0) return "";

  return html`
    <div class="panel recent-activity">
      <div class="panel__cap">
        <b>activity</b>
        <a class="panel__cap-right" href="/activity">all activity</a>
      </div>
      <div class="recent-activity__list">
        ${entries.map((entry) => {
          const authorMode = authorDisplayMode(entry.is_system, canViewProfiles);
          return html`
            <div
              class="recent-activity__row${entry.jurisdiction_path
                ? " recent-activity__row--linked"
                : ""}${entry.is_system ? " recent-activity__row--system" : ""}${entry.isFresh
                ? " recent-activity__row--fresh"
                : ""}"
            >
              <span class="recent-activity__at">${formatDate(entry.created_at)}</span>
              <span class="recent-activity__body">
                <!-- Actor first, unlike .recent-publications' passive phrasing —
                     that feed has no author at all, this one does. A system actor
                     names nobody: "edited Jane Doe", not "CivicPatch edited". -->
                ${authorMode === "link"
                  ? html`<a class="recent-activity__author" href="/~${entry.author_name}"
                      >${entry.author_name}</a
                    >`
                  : authorMode === "text"
                    ? html`<span class="recent-activity__author">${entry.author_name}</span>`
                    : ""}
                <span class="recent-activity__summary recent-activity__summary--${roleForType(entry.type)}"
                  >${entry.summary}</span
                >
                ${entry.jurisdiction_path
                  ? html`<a
                      class="recent-activity__jurisdiction"
                      href="/${jurisdictionOcdidToPath(entry.jurisdiction_path)}"
                      >${entry.jurisdiction_name}</a
                    >`
                  : entry.jurisdiction_name
                    ? html`<span>${entry.jurisdiction_name}</span>`
                    : ""}
              </span>
              <span class="recent-activity__commit">
                ${entry.pull_request_url
                  ? html`<a
                      class="recent-activity__pr"
                      href=${entry.pull_request_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      >commit</a
                    >`
                  : ""}
              </span>
              <span class="recent-activity__state"
                >${jurisdictionOcdidToState(entry.jurisdiction_ocdid).toUpperCase()}</span
              >
            </div>
          `;
        })}
      </div>
    </div>
  `;
}
