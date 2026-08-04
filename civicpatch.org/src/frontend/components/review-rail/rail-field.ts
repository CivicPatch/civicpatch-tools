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
  type DiffRecord,
  type FieldReason,
  type FieldSpec,
  type PresentRecord,
  type ScalarDiffState,
} from "../review/field-model.js";
import {
  buildFieldUpdate,
  displayScalar,
  withDisplayImage,
  renderScalarNewSide,
  renderDateNewSide,
  renderDivisionNewSide,
  renderSourceUrlsNewSide,
  renderPhotoNewSide,
  renderMultiList,
  type Save,
} from "../review/field-controls.js";
import { multiValueDiff } from "../review/field-model.js";

export const DASH = "—";

// The photo is the one field with no Restore (§5.1): the old side is a CDN
// copy and the new side a raw scrape URL, so there is nothing meaningful to put
// back — the field diffs on presence only.
const PHOTO_KEY = "image";

// Multi-value fields carry provenance on each row (§5.2 — `new` / unmarked /
// `dropped`), so a field-level "was" would encode the same fact twice, which is
// audit finding 4.
const CARRIES_OWN_PROVENANCE = new Set(["emails", "phones", "urls", "other_names", "source_urls"]);

export interface RailFieldProps {
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
}

function renderControl(props: RailFieldProps, record: PresentRecord) {
  const { field, oldRecord, state, error, save, isReadOnly, jurisdictionOcdid } = props;

  // Read-only renders every field as its value, never a disabled input (§10) —
  // but "its value" is not always text. displayScalar on the photo field returns
  // the image URL, which is not what a reader wants to see.
  if (isReadOnly) {
    if (field.type === "image") {
      return html`<person-image
        .person=${withDisplayImage(record)}
        .size=${"2.75rem"}
      ></person-image>`;
    }
    if (field.type === "multi") {
      const list = (diffValue(record, field) as string[]) ?? [];
      return list.length
        ? html`<span class="review-rail__readonly"
            >${list.map((value) => html`<span class="field-control__value">${value}</span>`)}</span
          >`
        : DASH;
    }
    return html`<span class="review-rail__readonly"
      >${displayScalar(field, record) || DASH}</span
    >`;
  }
  if (field.key === "office.division_ocdid")
    return renderDivisionNewSide(field, record, save, jurisdictionOcdid);
  if (field.key === "source_urls")
    return renderSourceUrlsNewSide(
      (diffValue(record, field) as string[]) ?? [],
      (values) => save({ source_urls: values }),
    );
  if (field.type === "image") return renderPhotoNewSide(record, save, isReadOnly);
  if (field.type === "multi") {
    // Derived every render from (current, old) rather than stamped when a row is
    // made — that is what makes editing a value until it matches a dropped one
    // clear that dropped row, and restore-then-remove return it, with no
    // bookkeeping (§5.2).
    const diff = multiValueDiff(
      (diffValue(oldRecord, field) as string[]) ?? [],
      (diffValue(record, field) as string[]) ?? [],
    );
    return renderMultiList(
      diff
        .filter((entry) => entry.status !== "removed")
        .map((entry) => ({ value: entry.value, isNew: entry.status === "added" })),
      diff.filter((entry) => entry.status === "removed").map((entry) => entry.value),
      (values) => save({ [field.key]: values }),
      field.label.toLowerCase(),
      field.key === "urls",
      field.key === "phones" ? "tel" : "text",
    );
  }
  if (field.type === "date") return renderDateNewSide(field, record, save);
  return renderScalarNewSide(field, record, save, { state, error });
}

// `was 2025 · Restore`. Absent when there is nothing to say: no old value, an
// unchanged field, a field that carries provenance per value, or the photo.
function renderWas(props: RailFieldProps) {
  const { field, oldRecord, newRecord, state, save, isReadOnly } = props;
  if (state === "same" || CARRIES_OWN_PROVENANCE.has(field.key)) return nothing;
  if (field.type === "multi") return nothing;

  const oldValue = diffValue(oldRecord, field);
  const oldText = oldRecord ? displayScalar(field, oldRecord) : "";
  if (!oldText.trim()) return nothing;

  const canRestore = !isReadOnly && !!newRecord && field.key !== PHOTO_KEY;
  return html`<div class="review-rail__was">
    <span class="review-rail__was-value">was ${oldText}</span>
    ${canRestore
      ? html`<button
          class="review-rail__restore"
          @click=${() => save(buildFieldUpdate(newRecord as PresentRecord, field.key, oldValue))}
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
function renderAttention(props: RailFieldProps) {
  const { reason, error, issueMessages } = props;

  if (error) {
    return html`<div class="review-rail__error">
      <i class="fa-solid fa-triangle-exclamation"></i><span>${error}</span>
    </div>`;
  }
  if (issueMessages.length) {
    return issueMessages.map(
      (message) => html`<div class="review-rail__issue">
        <i class="fa-solid fa-circle-exclamation"></i><span>${message}</span>
      </div>`,
    );
  }
  // Appeared as a task, and the task is done.
  if (reason === "error" || reason === "issue") {
    return html`<div class="review-rail__issue review-rail__resolved">
      <i class="fa-solid fa-circle-check"></i><span>Resolved</span>
    </div>`;
  }
  return nothing;
}

export function renderRailField(props: RailFieldProps) {
  const { field, newRecord, state } = props;
  return html`
    <div class="review-rail__field review-rail__field--${state}">
      <div class="review-rail__label">
        ${field.label}${field.required
          ? html` <span class="review-rail__req">*</span>`
          : nothing}
      </div>
      <!-- review-modal's focusOnOpen finds the field to focus by this attribute. -->
      <div class="review-rail__control" data-field=${field.key}>
        ${newRecord ? renderControl(props, newRecord) : DASH}
      </div>
      ${renderWas(props)} ${renderAttention(props)}
    </div>
  `;
}
