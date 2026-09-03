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

// Mirrors MEMBERSHIP_POST_FIELD in schemas/change_logs.py. An assignment whose `post_id`
// change carries a `before` vacated a seat; one without it is a first assignment.
const MEMBERSHIP_POST_FIELD = "post_id";

// Backend outcomes: `published`, `pending`, a DismissalReason, or `unknown`.
const PENDING_OUTCOME = "pending";
const SUPERSEDED_OUTCOME = "superseded";

// Collapsed rows stay one line tall; the rest are behind the disclosure.
const SHOWN_BADGES = 3;

export interface FieldChange {
  field: string;
  before?: unknown;
  after?: unknown;
}

export interface RosterChange {
  type: string;
  created_at: string;
  name: string;
  // The seat a membership names. Only assignments carry one — everything else is fully
  // described by its name plus the fields that moved.
  detail: string | null;
  fields: FieldChange[];
}

export interface TimelineEntry {
  changeset_id: string;
  created_at: string;
  updated_at: string;
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
  unchanged: "Unchanged",
  rejected: "Rejected",
  errored: "Errored",
  cancelled: "Cancelled",
  superseded: "Superseded",
  unknown: "Dismissed",
};

// Per-outcome, because "nothing changed" and "nothing was produced" are opposite results that
// a single line would flatten into the same sentence.
const QUIET_NOTE: Record<string, string> = {
  unchanged: "The roster was re-confirmed. Nothing to review.",
  errored: "The scrape failed before producing a roster.",
  cancelled: "Stopped before it produced a roster.",
  rejected: "Rejected without recorded roster changes.",
  unknown: "Dismissed with no recorded reason.",
};

const ADDED = { tone: "add", sigil: "+" };
const EDITED = { tone: "edit", sigil: "~" };
const REMOVED = { tone: "remove", sigil: "−" };
const MOVED = { tone: "move", sigil: "→" };

// `assign_membership` is absent: it is the one type whose verb depends on its fields.
const MARK_BY_TYPE: Record<string, { tone: string; sigil: string }> = {
  add_person: ADDED,
  edit_person: EDITED,
  delete_person: REMOVED,
  add_post: ADDED,
  edit_post: EDITED,
  delete_post: REMOVED,
  assert_field: EDITED,
  edit_jurisdiction: EDITED,
};

// What the change was about when it carries no field diff — `add_post` says "post", not "".
const NOUN_BY_TYPE: Record<string, string> = {
  add_person: "person",
  delete_person: "person",
  add_post: "post",
  delete_post: "post",
  assign_membership: "seat",
};

const movedSeat = (change: RosterChange): boolean =>
  change.fields.some(
    (f) => f.field === MEMBERSHIP_POST_FIELD && f.before != null,
  );

const markFor = (change: RosterChange) => {
  if (change.type === "assign_membership")
    return movedSeat(change) ? MOVED : ADDED;
  return MARK_BY_TYPE[change.type] ?? EDITED;
};

// The seat wins when there is one: "Ada Lovelace → Council D3" beats "Ada Lovelace → post_id".
// Otherwise one field names itself and several are counted — naming five makes the row
// unscannable, which is the thing the collapsed line exists to avoid.
const describeChange = (change: RosterChange): string => {
  if (change.detail) return change.detail;
  if (!change.fields.length) return NOUN_BY_TYPE[change.type] ?? "";
  if (change.fields.length === 1) return change.fields[0].field;
  return `${change.fields.length} fields`;
};

const renderBadge = (change: RosterChange) => {
  const mark = markFor(change);
  return html`
    <span class="change-badge change-badge--${mark.tone}">
      <span class="change-badge__sigil">${mark.sigil}</span>
      <span class="change-badge__who">${change.name}</span>
      <span class="change-badge__role">${describeChange(change)}</span>
    </span>
  `;
};

const renderChangeRow = (change: RosterChange) => {
  const mark = markFor(change);
  return html`
    <div class="tl-change tl-change--${mark.tone}">
      <span class="tl-change__sigil">${mark.sigil}</span>
      <span class="tl-change__who">${change.name}</span>
      <span class="tl-change__detail">
        ${change.fields.length
          ? change.fields.map(
              (field) => html`<span class="tl-change__field">
                ${field.field}: ${renderValue(field.before)} →
                ${renderValue(field.after)}
              </span>`,
            )
          : describeChange(change)}
      </span>
    </div>
  `;
};

const quietNote = (outcome: string) =>
  QUIET_NOTE[outcome] ?? "No roster changes.";

// "mayso-1@… → mayso-2@…" — what the badge cannot say.
//
// An empty array is a cleared value and has to read as one: joining it gives "", so the row
// rendered "emails: wtollett@… →" with nothing after the arrow, which looks truncated rather
// than deliberate. Empty and absent both show the dash.
const renderValue = (value: unknown): string => {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (value == null || value === "") return "—";
  return String(value);
};

function renderSummaryChanges(entry: TimelineEntry) {
  if (!entry.changes.length) {
    return html`<span class="runs-more">${quietNote(entry.outcome)}</span>`;
  }
  const hidden = entry.changes.length - SHOWN_BADGES;
  return html`
    ${entry.changes.slice(0, SHOWN_BADGES).map(renderBadge)}
    ${hidden > 0
      ? html`<span class="runs-more">+${hidden} more</span>`
      : nothing}
  `;
}

function renderChangeList(entry: TimelineEntry) {
  const hidden = entry.changes.slice(SHOWN_BADGES);
  if (!hidden.length) return nothing;
  return html`<div class="tl-changelist">${hidden.map(renderChangeRow)}</div>`;
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
            ${isSignedIn ? "Review →" : "Sign in to review"}
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
      <span>${durationBetween(entry.created_at, entry.updated_at)}</span>
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
