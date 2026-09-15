// One field's value, for the overview card — the full before/after, never capped or
// summarized to a field name the way the row-based overview used to. `<del>`/`<ins>`
// carry the diff itself; `renderRow`'s old badge-only "Post, Emails +2 more" list is gone.

import { html, nothing } from "lit-html";
import { displayScalar } from "../fields/field-controls.js";
import {
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

/** A changed multi-value field shows every value, marking which are new or gone; a changed
 * scalar shows both sides; anything else (same/added/cleared) just shows its one value. */
export function renderFieldValueDiff(
  field: FieldSpec,
  state: ScalarDiffState,
  oldRecord: DiffRecord,
  newRecord: DiffRecord,
) {
  return isMulti(field)
    ? renderMultiFieldDiff(field, oldRecord, newRecord)
    : renderScalarFieldDiff(field, oldRecord, newRecord, state);
}
