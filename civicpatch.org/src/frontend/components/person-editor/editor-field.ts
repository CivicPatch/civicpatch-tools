
import { html, nothing } from "lit-html";
import "../person-image.js";
import {
  diffValue,
  isContextField,
  isDate,
  isImage,
  isMulti,
  POST_FIELD,
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
  renderScalarNewSide,
  renderDateNewSide,
  renderPostPickNewSide,
  renderOfficeNewSide,
  renderPhotoNewSide,
  renderMultiList,
  type FocusRef,
  type Save,
} from "../fields/field-controls.js";
import { multiValueDiff } from "../fields/field-model.js";
import { type FieldAssertionSummary, type FieldLock } from "./field-provenance.js";
import "./assertions-popover.js";
import {
  heldPost,
  heldMembershipLabel,
  postLabelFor,
  type DerivedPost,
  type Post,
  type RoleOption,
} from "../posts-list/posts-model.js";

export const DASH = "—";

const PHOTO_KEY = "image";

const groupsControls = (field: FieldSpec) => isMulti(field) || isDate(field);

const CARRIES_OWN_PROVENANCE = new Set([
  "emails",
  "phones",
  "urls",
  "other_names",
  "source_urls",
]);

const LINK_TARGETS: Record<string, string> = {
  urls: PERSON_LINK_TARGET,
  source_urls: SOURCE_LINK_TARGET,
};

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
  posts: Post[];
  roles: RoleOption[];
  derivedPost: DerivedPost | null;
  focusRef: FocusRef | null;
  canAssignMembership: boolean;
  lock: FieldLock | null;
  assertionSummary: FieldAssertionSummary | null;
}

// A person already on the roster has a real membership `memberships.assign` can move — a
// not-yet-saved addition has none, so it keeps the plain local pick instead. `oldRecord` is
// the signal: `apply_people_patch` gives a brand-new person no base entry. Either way the
// pick stays local until save/publish; see `renderOfficeNewSide`.
function renderOfficeControl(props: EditorFieldProps, record: PresentRecord) {
  const {
    field,
    oldRecord,
    save,
    isReadOnly,
    posts,
    roles,
    derivedPost,
    focusRef,
    canAssignMembership,
  } = props;
  if (!oldRecord) {
    return isReadOnly
      ? html`<span class="person-editor__readonly"
          >${postLabelFor(diffValue(record, field), posts)}</span
        >`
      : renderPostPickNewSide(field, record, save, posts, derivedPost, focusRef);
  }
  const current = heldPost(oldRecord.memberships);
  if (!canAssignMembership) {
    return html`<span class="person-editor__readonly">${current?.label ?? DASH}</span>`;
  }
  return renderOfficeNewSide(
    record,
    save,
    posts,
    roles,
    current?.post_id ?? null,
    heldMembershipLabel(oldRecord.memberships),
    focusRef,
  );
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
    focusRef,
  } = props;
  if (field.key === POST_FIELD) return renderOfficeControl(props, record);
  if (isReadOnly) {
    if (isImage(field)) {
      return html`<person-image
        .person=${record}
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
  if (isImage(field)) return renderPhotoNewSide(record, save, isReadOnly);
  if (isMulti(field)) {
    const diff = multiValueDiff(
      (diffValue(oldRecord, field) as string[]) ?? [],
      (diffValue(record, field) as string[]) ?? [],
    );
    const present = diff.filter((entry) => entry.status !== "removed");
    const values = present.map((entry) => entry.value);
    return renderMultiList({
      rows: present.map((entry, index) => ({
        value: entry.value,
        isNew: entry.status === "added",
        isInvalid: !!rowError(field, values, index, record),
      })),
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

function renderWas(props: EditorFieldProps) {
  const { field, oldRecord, newRecord, state, save, isReadOnly } = props;
  if (state === "same" || CARRIES_OWN_PROVENANCE.has(field.key)) return nothing;
  if (isMulti(field)) return nothing;
  const oldValue = diffValue(oldRecord, field);
  const oldText = !oldRecord
    ? ""
    : field.key === POST_FIELD
      ? postLabelFor(diffValue(oldRecord, field), props.posts) ||
        (heldPost(oldRecord.memberships)?.label ?? "")
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

// To the right of the field: just the lock, plus the accept/reject values in a popover —
// <civ-assertions-popover> owns that interaction (open/fade state, its own hooks), not this
// file, which has none of its own.
function renderAssertionSummary(
  assertionSummary: FieldAssertionSummary | null,
  lock: FieldLock | null,
) {
  if (!lock) return nothing;
  return html`<civ-assertions-popover
    .lock=${lock}
    .summary=${assertionSummary}
  ></civ-assertions-popover>`;
}

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
  if (reason === "error" || reason === "issue") {
    return html`<div class="person-editor__issue person-editor__resolved">
      <i class="fa-solid fa-circle-check"></i><span>Resolved</span>
    </div>`;
  }
  return nothing;
}

export function renderEditorField(props: EditorFieldProps) {
  const { field, newRecord, state } = props;
  const grouped = !props.isReadOnly && groupsControls(field);
  return html`
    <div class="person-editor__field person-editor__field--${state}">
      <div class="person-editor__label">${field.label}${field.required
        ? html` <span class="person-editor__req">*</span>`
        : nothing}</div>
      <div
        class="person-editor__control"
        role=${grouped ? "group" : nothing}
        aria-label=${grouped ? field.label : nothing}
      >
        ${newRecord ? renderControl(props, newRecord) : DASH}
      </div>
      ${renderAssertionSummary(props.assertionSummary, props.lock)}
      ${renderWas(props)} ${renderAttention(props)}
    </div>
  `;
}
