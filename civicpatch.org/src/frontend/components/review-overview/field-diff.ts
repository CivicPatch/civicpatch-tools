// One field's value, for the overview card — the full before/after, never capped or
// summarized to a field name the way the row-based overview used to. `<del>`/`<ins>`
// carry the diff itself; `renderRow`'s old badge-only "Post, Emails +2 more" list is gone.

import { html, nothing } from "lit-html";
import "../person-image.js";
import { displayScalar } from "../fields/field-controls.js";
import {
  isImage,
  isMulti,
  multiValueDiff,
  type DiffRecord,
  type FieldSpec,
  type ScalarDiffState,
} from "../fields/field-model.js";
import { values } from "../review-preview/preview-values.js";

function renderMultiFieldDiff(
  field: FieldSpec,
  oldRecord: DiffRecord,
  newRecord: DiffRecord,
) {
  const diff = multiValueDiff(values(oldRecord, field), values(newRecord, field));
  return diff.map((entry, i) => {
    const value =
      entry.status === "removed"
        ? html`<del>${entry.value}</del>`
        : entry.status === "added"
          ? html`<ins>${entry.value}</ins>`
          : entry.value;
    return html`${i > 0 ? ", " : ""}${value}`;
  });
}

function renderScalarFieldDiff(
  field: FieldSpec,
  oldRecord: DiffRecord,
  newRecord: DiffRecord,
  state: ScalarDiffState,
) {
  if (state !== "changed") {
    const record = newRecord ?? oldRecord;
    return record ? displayScalar(field, record) : "";
  }
  const before = oldRecord ? displayScalar(field, oldRecord) : "";
  const after = newRecord ? displayScalar(field, newRecord) : "";
  return html`${before ? html`<del>${before}</del> ` : nothing}${after
    ? html`<ins>${after}</ins>`
    : nothing}`;
}

const PHOTO_SIZE = "2.5rem";

function renderPhoto(record: DiffRecord, caption: string) {
  return html`<person-image .person=${record} .size=${PHOTO_SIZE}></person-image>
    <span class="pv-photo__caption">${caption}</span>`;
}

// A photo is shown, not its url: the previous one struck out, the new one added.
function renderPhotoFieldDiff(
  oldRecord: DiffRecord,
  newRecord: DiffRecord,
  state: ScalarDiffState,
) {
  if (state === "same") {
    return html`<span class="pv-photo">${renderPhoto(newRecord ?? oldRecord, "now")}</span>`;
  }
  const before =
    (state === "changed" || state === "cleared") && oldRecord
      ? html`<del class="pv-photo">${renderPhoto(oldRecord, "was")}</del>`
      : nothing;
  const after =
    state !== "cleared" && newRecord
      ? html`<ins class="pv-photo">${renderPhoto(newRecord, "now")}</ins>`
      : nothing;
  return html`${before}${after}`;
}

/** A changed multi-value field shows every value, marking which are new or gone; a changed
 * scalar shows both sides; anything else (same/added/cleared) just shows its one value. */
export function renderFieldValueDiff(
  field: FieldSpec,
  state: ScalarDiffState,
  oldRecord: DiffRecord,
  newRecord: DiffRecord,
) {
  if (isImage(field)) return renderPhotoFieldDiff(oldRecord, newRecord, state);
  return isMulti(field)
    ? renderMultiFieldDiff(field, oldRecord, newRecord)
    : renderScalarFieldDiff(field, oldRecord, newRecord, state);
}
