// What one `change_logs` row did to a roster, in the two forms a page needs: a compact badge
// for a collapsed summary, and a full row for an expanded list.
//
// Shared because more than one page answers "what did this changeset do" — the jurisdiction
// timeline, and the cross-state changeset summaries. The mark logic is the reason they cannot
// each keep their own copy: which sigil a change earns is a domain rule, not styling.

import { html } from "lit-html";
import "./roster-change.css";

// Mirrors MEMBERSHIP_POST_FIELD in schemas/change_logs.py. An assignment whose `post_id`
// change carries a `before` vacated a seat; one without it is a first assignment.
const MEMBERSHIP_POST_FIELD = "post_id";

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
export const describeChange = (change: RosterChange): string => {
  if (change.detail) return change.detail;
  if (!change.fields.length) return NOUN_BY_TYPE[change.type] ?? "";
  if (change.fields.length === 1) return change.fields[0].field;
  return `${change.fields.length} fields`;
};

// "emails: a@x.gov -> b@x.gov", which the badge cannot say.
//
// An empty array is a cleared value and has to read as one: joining it gives "", so the row
// rendered "emails: wtollett@… →" with nothing after the arrow, which looks truncated rather
// than deliberate. Empty and absent both show the dash.
const renderValue = (value: unknown): string => {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "(none)";
  if (value == null || value === "") return "(none)";
  return String(value);
};

export const renderChangeBadge = (change: RosterChange) => {
  const mark = markFor(change);
  return html`
    <span class="change-badge change-badge--${mark.tone}">
      <span class="change-badge__sigil">${mark.sigil}</span>
      <span class="change-badge__who">${change.name}</span>
      <span class="change-badge__role">${describeChange(change)}</span>
    </span>
  `;
};

export const renderChangeRow = (change: RosterChange) => {
  const mark = markFor(change);
  return html`
    <div class="change-row change-row--${mark.tone}">
      <span class="change-row__sigil">${mark.sigil}</span>
      <span class="change-row__who">${change.name}</span>
      <span class="change-row__detail">
        ${change.fields.length
          ? change.fields.map(
              (field) => html`<span class="change-row__field">
                ${field.field}: ${renderValue(field.before)} →
                ${renderValue(field.after)}
              </span>`,
            )
          : describeChange(change)}
      </span>
    </div>
  `;
};
