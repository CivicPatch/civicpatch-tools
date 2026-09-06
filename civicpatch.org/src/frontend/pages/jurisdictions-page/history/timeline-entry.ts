// One changeset on a jurisdiction's timeline: what it was, how it ended, and what it did to
// the roster. Collapsed to a scannable line, expanded to the full list.
//
// Replaces civ-history-modal — the ids it showed live in the expanded body, behind the admin
// check, rather than behind a second surface reached by clicking a date.

import { component } from "haunted";
import { html, nothing } from "lit-html";
import "./timeline.css";
import {
  dateStringToFriendly,
  durationBetween,
} from "../../../utils/date-utils.js";
import { jurisdictionOcdidToState } from "../../../components/ocdid-utils.js";
import { LOGIN_PATH, reviewSessionUrl } from "../../review-routes.js";
import {
  renderChangeBadge,
  renderChangeRow,
  type RosterChange,
} from "../../../components/roster-change/index.js";

// Re-exported: `timeline.ts` and the history page type their entries from here, and a roster
// change is part of that shape.
export type { FieldChange, RosterChange } from "../../../components/roster-change/index.js";

// Backend outcomes: `published`, `pending`, a DismissalReason, or `unknown`.
const PENDING_OUTCOME = "pending";
const SUPERSEDED_OUTCOME = "superseded";

// Collapsed rows stay one line tall; the rest are behind the disclosure.
const SHOWN_BADGES = 3;

export interface TimelineEntry {
  changeset_id: string;
  created_at: string;
  updated_at: string;
  pipeline_run_started_at?: string | null;
  pipeline_run_finished_at?: string | null;
  dismissed_reason?: string | null;
  issue_types?: string[];
  kind: string | null;
  change_url: string | null;
  outcome: string;
  resolved_by: string | null;
  pipeline_run_status: string | null;
  changes: RosterChange[];
}

const KIND_LABEL: Record<string, string> = {
  scrape: "Scrape",
  sheet_import: "Import",
  people_edit: "Edit",
  jurisdiction_edit: "Details",
};

const OUTCOME_LABEL: Record<string, string> = {
  published: "Published",
  pending: "Awaiting review",
  rejected: "Rejected",
  errored: "Errored",
  cancelled: "Cancelled",
  superseded: "Superseded",
  unknown: "Dismissed",
};

// Per-outcome, because "nothing changed" and "nothing was produced" are opposite results that
// a single line would flatten into the same sentence.
const QUIET_NOTE: Record<string, string> = {
  // A scrape that re-confirms the roster publishes, moving nothing — the most common scrape
  // outcome, which without this read "No roster changes."
  published: "The roster was re-confirmed. Nothing to review.",
  errored: "The scrape failed before producing a roster.",
  cancelled: "Stopped before it produced a roster.",
  rejected: "Rejected. Nothing it proposed was applied.",
  unknown: "Dismissed with no recorded reason.",
};

const quietNote = (outcome: string) =>
  QUIET_NOTE[outcome] ?? "No roster changes.";

// Only a scrape has a pipeline run. An import or a hand edit has no duration to report, and
// the changeset's own timestamps are not one — it is minted at ingest with created_at ==
// updated_at, which read 0s for a run that took nine minutes.
const pipelineRunDuration = (entry: TimelineEntry) =>
  entry.pipeline_run_started_at && entry.pipeline_run_finished_at
    ? durationBetween(entry.pipeline_run_started_at, entry.pipeline_run_finished_at)
    : null;

const ISSUE_LABEL: Record<string, string> = {
  cost_cap_reached: "stopped at its cost cap",
  no_roster_found: "found no roster",
  domain_inactive: "domain inactive",
  domain_navigation_error: "could not navigate the site",
  pipeline_error: "pipeline error",
  merge_failed: "merge failed",
  user_reported: "reported by a reviewer",
};

// The issues still open on this changeset. Without them, a short roster and a complete one look
// identical on the timeline.
function renderIssues(entry: TimelineEntry) {
  const types = entry.issue_types ?? [];
  if (!types.length) return nothing;
  return html`
    <span class="tl-entry__issues">
      ${types.map((t) => ISSUE_LABEL[t] ?? t).join(", ")}
    </span>
  `;
}

function renderSummaryChanges(entry: TimelineEntry) {
  if (!entry.changes.length) {
    return html`
      <span class="runs-more">${quietNote(entry.outcome)}</span>
      ${renderIssues(entry)}
    `;
  }
  const hidden = entry.changes.length - SHOWN_BADGES;
  return html`
    ${entry.changes.slice(0, SHOWN_BADGES).map(renderChangeBadge)}
    ${hidden > 0
      ? html`<span class="runs-more">+${hidden} more</span>`
      : nothing}
    ${renderIssues(entry)}
  `;
}

function renderChangeList(entry: TimelineEntry) {
  const hidden = entry.changes.slice(SHOWN_BADGES);
  if (!hidden.length) return nothing;
  return html`<div class="change-list">${hidden.map(renderChangeRow)}</div>`;
}

function renderActions(
  entry: TimelineEntry,
  isSignedIn: boolean,
  ocdid: string,
) {
  const isPending = entry.outcome === PENDING_OUTCOME;
  const reviewHref = isSignedIn
    ? reviewSessionUrl(jurisdictionOcdidToState(ocdid), entry.changeset_id)
    : LOGIN_PATH;

  return html`
    <div class="tl-actions">
      ${isPending
        ? html`<a class="btn-primary" href=${reviewHref}>
            ${isSignedIn
              ? html`Review <i class="fa-solid fa-arrow-right"></i>`
              : "Sign in to review"}
          </a>`
        : nothing}
      ${entry.change_url
        ? html`<a
            href=${entry.change_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            <i class="fa-brands fa-github"></i> View change
          </a>`
        : nothing}
      ${entry.resolved_by
        ? html`<span class="tl-quiet">
            ${entry.outcome === "published" ? "Published" : "Dismissed"} by
            ${entry.resolved_by}.
          </span>`
        : nothing}
    </div>
  `;
}

// Everything civ-history-modal showed. Admin-gated: ids are debugging material, not content.
function renderIds(entry: TimelineEntry, isAdmin: boolean) {
  if (!isAdmin) return nothing;
  return html`
    <div class="tl-ids">
      <span>changeset ${entry.changeset_id}</span>
      ${entry.pipeline_run_status
        ? html`<span>${entry.pipeline_run_status}</span>`
        : nothing}
      ${pipelineRunDuration(entry)
        ? html`<span>${pipelineRunDuration(entry)}</span>`
        : nothing}
      <span>outcome ${entry.outcome}</span>
    </div>
  `;
}

type TimelineEntryProps = {
  entry: TimelineEntry;
  isAdmin: boolean;
  isSignedIn: boolean;
  jurisdictionOcdid: string;
};

function CivTimelineEntry({
  entry,
  isAdmin,
  isSignedIn,
  jurisdictionOcdid,
}: TimelineEntryProps) {
  if (!entry) return html``;

  // Demoted, not hidden: a superseded run still happened, and hiding it makes the page lie
  // about what ran. Decision 3.
  const demoted = entry.outcome === SUPERSEDED_OUTCOME;

  return html`
    <details class="tl-entry ${demoted ? "tl-entry--superseded" : ""}">
      <summary class="tl-entry__summary">
        <span class="tl-entry__when"
          >${dateStringToFriendly(entry.created_at)}</span
        >
        <span class="tl-entry__kind"
          >${KIND_LABEL[entry.kind ?? "scrape"] ?? entry.kind}</span
        >
        <span class="tl-entry__pill">
          <span class="runs-pill runs-pill--${entry.outcome}">
            ${OUTCOME_LABEL[entry.outcome] ?? entry.outcome}
          </span>
        </span>
        <span class="tl-entry__changes">${renderSummaryChanges(entry)}</span>
      </summary>
      <div class="tl-entry__body">
        ${renderChangeList(entry)}
        ${renderActions(entry, isSignedIn, jurisdictionOcdid)}
        ${renderIds(entry, isAdmin)}
      </div>
    </details>
  `;
}

customElements.define(
  "civ-timeline-entry",
  component(CivTimelineEntry as any, { useShadowDOM: false }),
);
