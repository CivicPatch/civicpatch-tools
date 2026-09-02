// One person, editable: a fixed-width identity column and a field body (§5).
//
// Only the frozen visible fields render, plus an expander for the rest. The
// frozen set is passed in rather than computed here — three views have to agree
// on it and a tab switch must not recompute it (§2.1), so the review-session
// page owns it.

import { html, nothing } from "lit-html";
import "../person-image.js";
import "./person-editor.css";
import type { DerivedPost, Post } from "../posts-list/posts-model.js";
import {
  provenanceLabel,
  type PersonAssertion,
} from "./field-provenance.js";
import {
  FIELD_SCHEMA,
  isContextField,
  type DiffRecord,
  type FieldReason,
  type Issue,
  type SurvivingField,
} from "../fields/field-model.js";
import { focusedKey } from "./editor-focus.js";
import { withDisplayImage, type FieldFocus, type Save } from "../fields/field-controls.js";
import { renderEditorField } from "./editor-field.js";
import {
  DEPARTING,
  PersonStatus,
  STATUS_LABEL,
  type PersonStatusKey,
  type PersonCard,
} from "../people/person-cards.js";
import { renderPersonFace } from "../review/person-face.js";
import { editorSummary } from "./editor-summary.js";

const BANNER: Record<string, { title: string; body: string }> = {
  [PersonStatus.REMOVED]: {
    title: "Not found in this scrape.",
    body: "The scraper didn't see them on the source site, so publishing will drop them. Check whether they left office — or whether the scraper missed them.",
  },
  [PersonStatus.DELETED]: {
    title: "You removed this person.",
    body: "Publishing will drop their record.",
  },
};

export interface PersonEditorProps {
  status: PersonStatusKey;
  oldRecord: DiffRecord;
  newRecord: DiffRecord;
  surviving: SurvivingField[];
  frozenReasons: Map<string, FieldReason>;
  issues: Issue[];
  isReadOnly: boolean;
  jurisdictionOcdid: string | null | undefined;
  // "Council President, Ward 9". Passed in rather than read off the record: a proposed person
  // holds no membership yet, and only the proposal knows their post.
  subtitle: string;
  // The accepts on each of this person's fields, for the per-field tags.
  accepts: Map<string, PersonAssertion[]>;
  posts: Post[];
  // The derivation's post, shown when nobody has picked one. Never saved.
  derivedPost: DerivedPost | null;
  onAddPost: () => void;
  // Clear-on-edit: once the reviewer touches a card its markers are presumed
  // addressed and drop away. §2.2 refines this to per-field (the *anchored* field
  // being edited); that lands with the checklist in §17 step 8, when ticking
  // gives the other half of the rule somewhere to live.
  isDirty: boolean;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onSave: Save;
  onRemove: () => void;
  onUnremove: () => void;
  onRestore: () => void;
  onReset: (() => void) | null;
  // "This record and another are the same person." Offered on every card the
  // reviewer has not already decided about; false when nobody else is left to
  // merge with.
  // Step 1 of a merge happens in place: the button opens a strip of the other
  // people on this card, so nothing stacks on top of whatever you are already in.
  mergeCandidates: PersonCard[];
  isCandidateListOpen: boolean;
  onToggleCandidates: () => void;
  onPickPartner: (partnerId: string) => void;
  // The field to open with the caret in, if any. Null everywhere the editor is a
  // list — only the modal opens on a field.
  focusField: FieldFocus | null;
}


// `size` has to be a property binding: person-image declares no
// observedAttributes, so size="3rem" is silently ignored and it falls back to
// its 2rem default.
//
// Bigger than it was, but not column-wide: name and office stack under the
// photo, so a photo that fills the column makes the identity side taller than
// the fields beside it and a four-field card 300px tall. It cannot be set in
// CSS — person-image writes width/height as inline styles.
const PHOTO_SIZE = "7.5rem";

function renderIdentity(props: PersonEditorProps) {
  const { status, oldRecord, newRecord, subtitle } = props;
  const record = newRecord ?? oldRecord;
  const name = record?.name || "(unnamed)";

  return html`
    <div class="person-editor__identity">
      <person-image
        .person=${withDisplayImage(record)}
        .size=${PHOTO_SIZE}
      ></person-image>
      <div class="person-editor__name">${name}</div>
      <div class="person-editor__office">${subtitle || nothing}</div>
    </div>
  `;
}

// How much work this card holds, and what can be done to it as a whole. Rendered into the
// modal's own header rather than here: the editor has one mount now, and two stacked headers
// read as two separate things with a gap between them.
//
// The person-level controls live here rather than under the photo: they act on the whole
// card, and the identity column is about who this is.
//
// The summary replaces the status label rather than joining it: "changed" next to "2 fields
// changed" is the same fact twice, and only one of them tells you how much work the card holds.
export function renderPersonSummary(props: PersonEditorProps) {
  const { status, surviving, issues, isDirty, isReadOnly } = props;
  return html`
    <span class="editor-summary"
      >${editorSummary({ status, surviving, issues, isDirty })}</span
    >
    ${isReadOnly ? nothing : renderActions(props, DEPARTING.has(status))}
  `;
}

// Step 1 of a merge, opened by the button directly above it — a strip of the
// other people on this card, in place, so nothing stacks on top of whatever the
// reviewer is already in.
function renderMergeCandidates(props: PersonEditorProps) {
  if (props.isReadOnly || !props.isCandidateListOpen || !props.mergeCandidates.length) return nothing;
  return html`
    <div class="person-editor__merge-with">
      <span class="person-editor__merge-lede">Which record is the same person?</span>
      <div class="person-editor__merge-faces">
        ${props.mergeCandidates.map((card) => renderPersonFace(card, props.onPickPartner))}
      </div>
    </div>
  `;
}

function renderActions(props: PersonEditorProps, departing: boolean) {
  const { status, onRemove, onUnremove, onRestore, onReset } = props;

  // One button, two operations. A scrape-dropped person has no record to
  // un-flag, so restoring them rebuilds it from the old side; a reviewer-removed
  // one just loses the flag (§12).
  if (departing) {
    const restore = status === PersonStatus.REMOVED ? onRestore : onUnremove;
    return html`<div class="person-editor__actions">
      <button class="person-editor__restore-person" @click=${restore}>
        Restore
      </button>
    </div>`;
  }

  return html`<div class="person-editor__actions">
    ${onReset
      ? html`<button class="person-editor__reset" @click=${onReset}>Reset</button>`
      : nothing}
    <button class="person-editor__delete" @click=${onRemove}>Remove</button>
    ${props.mergeCandidates.length
      ? html`<button
          class="person-editor__merge"
          aria-expanded=${props.isCandidateListOpen}
          @click=${props.onToggleCandidates}
        >
          Merge with…
        </button>`
      : nothing}
  </div>`;
}

// A departing person is one decision, not eleven fields. Their details stay
// available behind the expander rather than being spent by default.
function renderBanner(props: PersonEditorProps) {
  const { status, isExpanded, onToggleExpand } = props;
  const copy = BANNER[status];
  return html`
    <div class="person-editor__banner">
      <span class="person-editor__banner-title">${copy.title}</span>
      <span>${copy.body}</span>
    </div>
    <button class="person-editor__expander" @click=${onToggleExpand}>
      ${isExpanded ? "Hide their details" : "Show their details"}
    </button>
  `;
}

// Issues that anchor to no field belong to the person, so they sit above the
// field list rather than under any row.
function renderRowIssues(props: PersonEditorProps) {
  if (props.isDirty) return nothing;
  return props.issues
    .filter((issue) => !issue.field)
    .map(
      (issue) => html`<div class="person-editor__issue person-editor__issue--row">
        <i class="fa-solid fa-circle-exclamation"></i><span>${issue.message}</span>
      </div>`,
    );
}

function renderFields(props: PersonEditorProps, keys: Set<string>) {
  const {
    oldRecord,
    newRecord,
    surviving,
    issues,
    isReadOnly,
    jurisdictionOcdid,
    posts,
    derivedPost,
    onAddPost,
    onSave,
  } = props;
  const survivingByKey = new Map(surviving.map((s) => [s.field.key, s]));
  const fields = FIELD_SCHEMA.filter((field) => keys.has(field.key));
  const focus = props.focusField;
  const focusKey = focusedKey(fields, focus);

  return fields.map((field) => {
    const current = survivingByKey.get(field.key);
    return renderEditorField({
      field,
      oldRecord,
      newRecord,
      // A field can be frozen visible while no longer surviving on its own — a
      // fixed error is the whole point of the one-directional rule (§2.1).
      state: current?.state ?? "same",
      reason: props.frozenReasons.get(field.key) ?? "diff",
      error: current?.error ?? null,
      issueMessages: props.isDirty
        ? []
        : issues.filter((issue) => issue.field === field.key).map((issue) => issue.message),
      save: onSave,
      provenance: provenanceLabel(props.accepts.get(field.key)),
      isReadOnly,
      jurisdictionOcdid,
      posts,
      derivedPost,
      onAddPost,
      focusRef: focus && field.key === focusKey ? focus.attach : null,
    });
  });
}

// Someone with nothing to review is one line, not a card. The collapse rule
// already empties their field body; without this the identity column still sets
// a full block of height, so a 20-person council scrolls past ~15 blocks that
// say nothing to reach the few that changed. §4 already applies the same
// reasoning to Overview's unchanged group ("a face strip … without spending a
// card each"); this is that, in Detail.
//
// It stays in slot order and stays expandable, so §5's one ungrouped list is
// intact — it just stops spending a card on people with nothing to say.
function renderStrip(props: PersonEditorProps) {
  const { status, oldRecord, newRecord, onToggleExpand, subtitle } = props;
  const record = newRecord ?? oldRecord;
  return html`
    <div class="person-editor person-editor--strip person-editor--${status}">
      <person-image
        .person=${withDisplayImage(record)}
        .size=${"2.75rem"}
      ></person-image>
      <span class="person-editor__name">${record?.name || "(unnamed)"}</span>
      <span class="person-editor__office">${subtitle || nothing}</span>
      <span class="person-editor__status">${STATUS_LABEL[status]}</span>
      <button class="person-editor__expander" @click=${onToggleExpand}>Show fields</button>
    </div>
  `;
}

export function renderPersonEditor(props: PersonEditorProps) {
  const { status, frozenReasons, isExpanded, onToggleExpand } = props;
  const departing = DEPARTING.has(status);

  const visibleKeys = new Set(frozenReasons.keys());
  const hiddenCount = FIELD_SCHEMA.length - visibleKeys.size;
  const keys = isExpanded ? new Set(FIELD_SCHEMA.map((f) => f.key)) : visibleKeys;

  // Context fields are always visible, so counting them here would mean nobody
  // ever collapses to a strip — which is what happened once source urls became
  // always-visible. `needsReview` makes the same exclusion for the same reason.
  // An errored context field is the exception: it blocks publish, so folding it
  // into a one-line strip would hide the reason the button is disabled.
  const hasReviewableField = FIELD_SCHEMA.some(
    (field) =>
      visibleKeys.has(field.key) &&
      (!isContextField(field) || frozenReasons.get(field.key) === "error"),
  );

  if (!departing && !hasReviewableField && !isExpanded) return renderStrip(props);

  return html`
    <div class="person-editor person-editor--${status}">
      ${renderMergeCandidates(props)} ${renderIdentity(props)}
      <div class="person-editor__fields">
        ${renderRowIssues(props)}
        ${departing
          ? renderBanner(props)
          : nothing}
        ${departing && !isExpanded ? nothing : renderFields(props, keys)}
        ${!departing && hiddenCount > 0
          ? html`<button class="person-editor__expander" @click=${onToggleExpand}>
              ${isExpanded
                ? "Hide unchanged fields"
                : `+ ${hiddenCount} unchanged field${hiddenCount === 1 ? "" : "s"}`}
            </button>`
          : nothing}
      </div>
    </div>
  `;
}