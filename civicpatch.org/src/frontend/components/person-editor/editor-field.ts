// One field of one person, as `label | control | was … Restore` (spec §5).
//
// This is the shape that replaces the diff's `old | copy | new`: the old value
// is a trailing annotation, not a second column, so every control starts at the
// same x down the whole card. §21.5 is the other reason — a merge picker is
// `A | B | C → chosen`, so the *controls* must stay free of any assumption that
// there are exactly two sides. They live in field-controls.ts and know nothing
// about old records; this module is the only place that pairs them.

import { html, nothing } from "lit-html";
import "../person-image.js";
import {
  diffValue,
  isContextField,
  isDate,
  isImage,
  isMulti,
  rowError,
  type DiffRecord,
  type FieldReason,
  type FieldSpec,
  type PresentRecord,
  type ScalarDiffState,
} from "../fields/field-model.js";
import {
  PERSON_LINK_TARGET,
  SOURCE_LINK_TARGET,
} from "../../utils/source-links.js";
import {
  buildFieldUpdate,
  displayScalar,
  withDisplayImage,
  renderScalarNewSide,
  renderDateNewSide,
  renderPostNewSide,
  renderPhotoNewSide,
  renderMultiList,
  type FocusRef,
  type Save,
} from "../fields/field-controls.js";
import { multiValueDiff } from "../fields/field-model.js";
import { postLabelFor, type Post } from "../posts-list/posts-model.js";

export const DASH = "—";

// The photo is the one field with no Restore (§5.1): the old side is a CDN
// copy and the new side a raw scrape URL, so there is nothing meaningful to put
// back — the field diffs on presence only.
const PHOTO_KEY = "image";

const POST_KEY = "post_id";

// A field that renders several controls has to hang its label on the set — the
// label is "Term start", but no one input is that; they are its year and month.
const groupsControls = (field: FieldSpec) => isMulti(field) || isDate(field);

// Multi-value fields carry provenance on each row (§5.2 — `new` / unmarked /
// `dropped`), so a field-level "was" would encode the same fact twice, which is
// audit finding 4.
const CARRIES_OWN_PROVENANCE = new Set([
  "emails",
  "phones",
  "urls",
  "other_names",
  "source_urls",
]);

// Which multi-value fields are followable, and in whose window. A person's links
// and the sources they were read from deliberately do not share a tab.
const LINK_TARGETS: Record<string, string> = {
  urls: PERSON_LINK_TARGET,
  source_urls: SOURCE_LINK_TARGET,
};

// For the soft keyboard, not for validation — format is checked in field-model,
// where it can also block Publish. Url fields stay `text`: the browser's own
// bubble would report a second, differently-worded verdict on the same value.
const INPUT_TYPES: Record<string, string> = {
  phones: "tel",
  emails: "email",
};

export interface EditorFieldProps {
  field: FieldSpec;
  oldRecord: DiffRecord;
  newRecord: DiffRecord;
  state: ScalarDiffState;
  reason: FieldReason;
  error: string | null;
  issueMessages: string[];
  save: Save;
  isReadOnly: boolean;
  jurisdictionOcdid: string | null | undefined;
  // Every post in the jurisdiction. Empty until the read lands; the control still shows the
  // record's own value.
  posts: Post[];
  // The derivation's seat, shown as the Post field's value when nobody has picked one.
  derivedPostId: string | null;
  // Non-null on the one field the view opened on, so the control it belongs to
  // can take focus. The editor picks the row; the control picks the element.
  focusRef: FocusRef | null;
  provenance: string | null;
}

function renderControl(props: EditorFieldProps, record: PresentRecord) {
  const {
    field,
    oldRecord,
    state,
    error,
    save,
    isReadOnly,
    jurisdictionOcdid,
    posts,
    derivedPostId,
    focusRef,
  } = props;

  // Read-only renders every field as its value, never a disabled input (§10) —
  // but "its value" is not always text. displayScalar on the photo field returns
  // the image URL, which is not what a reader wants to see.
  if (isReadOnly) {
    // A post is stored by id, so the generic scalar path would print a UUID.
    if (field.key === POST_KEY) {
      return html`<span class="person-editor__readonly"
        >${postLabelFor(diffValue(record, field), posts)}</span
      >`;
    }
    if (isImage(field)) {
      return html`<person-image
        .person=${withDisplayImage(record)}
        .size=${"2.75rem"}
      ></person-image>`;
    }
    if (isMulti(field)) {
      const list = (diffValue(record, field) as string[]) ?? [];
      return list.length
        ? html`<span class="person-editor__readonly"
            >${list.map(
              (value) =>
                html`<span class="field-control__value">${value}</span>`,
            )}</span
          >`
        : DASH;
    }
    return html`<span class="person-editor__readonly"
      >${displayScalar(field, record) || DASH}</span
    >`;
  }
  if (field.key === POST_KEY)
    return renderPostNewSide(field, record, save, posts, derivedPostId, focusRef);
  if (isImage(field)) return renderPhotoNewSide(record, save, isReadOnly);
  if (isMulti(field)) {
    // Derived every render from (current, old) rather than stamped when a row is
    // made — that is what makes editing a value until it matches a dropped one
    // clear that dropped row, and restore-then-remove return it, with no
    // bookkeeping (§5.2).
    const diff = multiValueDiff(
      (diffValue(oldRecord, field) as string[]) ?? [],
      (diffValue(record, field) as string[]) ?? [],
    );
    // A duplicate is a property of the list, so the rows have to be judged
    // together — hence the values array rather than a per-entry check.
    const present = diff.filter((entry) => entry.status !== "removed");
    const values = present.map((entry) => entry.value);
    return renderMultiList({
      rows: present.map((entry, index) => ({
        value: entry.value,
        isNew: entry.status === "added",
        isInvalid: !!rowError(field, values, index, record),
      })),
      // A context field is never compared, so it has nothing to have dropped.
      dropped: isContextField(field)
        ? []
        : diff
            .filter((entry) => entry.status === "removed")
            .map((entry) => entry.value),
      setValues: (values) => save({ [field.key]: values }),
      label: field.label.toLowerCase(),
      linkTarget: LINK_TARGETS[field.key] ?? null,
      inputType: INPUT_TYPES[field.key] ?? "text",
      focusRef,
    });
  }
  if (isDate(field)) return renderDateNewSide(field, record, save, focusRef);
  return renderScalarNewSide(field, record, save, { state, error }, focusRef);
}

// `was 2025, Restore`. Absent when there is nothing to say: no old value, an
// unchanged field, a field that carries provenance per value, or the photo.
function renderWas(props: EditorFieldProps) {
  const { field, oldRecord, newRecord, state, save, isReadOnly } = props;
  if (state === "same" || CARRIES_OWN_PROVENANCE.has(field.key)) return nothing;
  if (isMulti(field)) return nothing;

  const oldValue = diffValue(oldRecord, field);
  // Same reason as the read-only branch: "was a3f2c1…" tells a reviewer nothing.
  const oldText = !oldRecord
    ? ""
    : field.key === POST_KEY
      ? postLabelFor(diffValue(oldRecord, field), props.posts)
      : displayScalar(field, oldRecord);
  if (!oldText.trim()) return nothing;

  const canRestore = !isReadOnly && !!newRecord && field.key !== PHOTO_KEY;
  return html`<div class="person-editor__was">
    <span class="person-editor__was-value">was ${oldText}</span>
    ${canRestore
      ? html`<button
          class="person-editor__restore"
          @click=${() =>
            save(
              buildFieldUpdate(newRecord as PresentRecord, field.key, oldValue),
            )}
        >
          Restore
        </button>`
      : nothing}
  </div>`;
}

// Why the field is on screen, as the badge for its current condition. The reason
// is frozen at first appearance (§2.2); the badge is derived, so a field that
// surfaced because of an error stays visible and reads `resolved` once fixed
// rather than vanishing at the moment the reviewer fixed it.
function renderAttention(props: EditorFieldProps) {
  const { reason, error, issueMessages } = props;

  if (error) {
    return html`<div class="person-editor__error">
      <i class="fa-solid fa-triangle-exclamation"></i><span>${error}</span>
    </div>`;
  }
  if (issueMessages.length) {
    return issueMessages.map(
      (message) =>
        html`<div class="person-editor__issue">
          <i class="fa-solid fa-circle-exclamation"></i><span>${message}</span>
        </div>`,
    );
  }
  // Appeared as a task, and the task is done.
  if (reason === "error" || reason === "issue") {
    return html`<div class="person-editor__issue person-editor__resolved">
      <i class="fa-solid fa-circle-check"></i><span>Resolved</span>
    </div>`;
  }
  // Editor only. Preview carries no diff vocabulary, and this is exactly that.
  if (props.provenance) {
    return html`<div class="person-editor__provenance">
      ${props.provenance}
    </div>`;
  }
  return nothing;
}

export function renderEditorField(props: EditorFieldProps) {
  const { field, newRecord, state } = props;
  // Read-only renders values, not controls, so there is no set to name.
  const grouped = !props.isReadOnly && groupsControls(field);
  return html`
    <div class="person-editor__field person-editor__field--${state}">
      <div class="person-editor__label">
        ${field.label}${field.required
          ? html` <span class="person-editor__req">*</span>`
          : nothing}
      </div>
      <div
        class="person-editor__control"
        role=${grouped ? "group" : nothing}
        aria-label=${grouped ? field.label : nothing}
      >
        ${newRecord ? renderControl(props, newRecord) : DASH}
      </div>
      ${renderWas(props)} ${renderAttention(props)}
    </div>
  `;
}
