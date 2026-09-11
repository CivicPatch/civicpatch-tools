import { html } from "lit-html";
import "../../components/panel/panel.css";
import "./recent-activity.css";
import {
  jurisdictionOcdidToPath,
  jurisdictionOcdidToState,
} from "../../components/ocdid-utils.js";
import type { RecentActivityEntry } from "./use-recent-activity.ts";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
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
        ${entries.map(
          (entry) => html`
            <div
              class="recent-activity__row${entry.jurisdiction_path
                ? " recent-activity__row--linked"
                : ""}${entry.is_system ? " recent-activity__row--system" : ""}"
            >
              <span class="recent-activity__at">${formatDate(entry.created_at)}</span>
              <span class="recent-activity__body">
                <!-- Actor first, unlike .recent-publications' passive phrasing —
                     that feed has no author at all, this one does. A system actor
                     names nobody: "edited Jane Doe", not "CivicPatch edited". -->
                ${canViewProfiles && !entry.is_system
                  ? html`<a class="recent-activity__author" href="/~${entry.author_name}"
                      >${entry.author_name}</a
                    >`
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
                      >PR</a
                    >`
                  : ""}
              </span>
              <span class="recent-activity__state"
                >${jurisdictionOcdidToState(entry.jurisdiction_ocdid).toUpperCase()}</span
              >
            </div>
          `,
        )}
      </div>
    </div>
  `;
}
