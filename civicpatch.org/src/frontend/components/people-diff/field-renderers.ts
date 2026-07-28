// The two-column diff row: `label | old | copy-gutter | new`. Everything here
// exists because today's Detail shows an old side beside a new one — the grid,
// the strikethrough, the copy arrow. The controls that go in the new cell live
// in field-controls.ts and carry no two-sided assumption, so they outlive this.

import { html } from "lit-html";
import "../person-image.js";
import {
  diffValue,
  fieldDiffState,
  fieldError,
  multiValueState,
  normalizeMultiValue,
  type FieldSpec,
} from "./diff-model.js";
import {
  buildFieldUpdate,
  displayScalar,
  renderScalarNewSide,
  renderDateNewSide,
  renderMultiNewSide,
  renderDivisionNewSide,
  renderSourceUrlsNewSide,
  renderPhotoNewSide,
  sourceLinks,
  type NewSideRenderer,
  type Save,
} from "./field-controls.js";

export const DASH = "—";

export type { Save };

// ── Shared row scaffold ──────────────────────────────────────────────────────
// Every field is `label | old | copy-gutter | new`. Each field type supplies
// only its old/new content (+ optional copy arrow + error); this owns the grid.

function renderLabel(field: FieldSpec) {
  return html`${field.label}${field.required
    ? html` <span class="people-diff__req">*</span>`
    : ""}`;
}

export function copyArrow(show: boolean, onCopy: () => void) {
  return show
    ? html`<button
        class="people-diff__copy"
        title="copy old → new"
        @click=${onCopy}
      >
        <i class="fa-solid fa-arrow-right"></i>
      </button>`
    : "";
}

function fieldRow(
  field: FieldSpec,
  state: string,
  parts: { old: unknown; copy?: unknown; new: unknown; error?: string | null },
) {
  return html`
    <div class="people-diff__field people-diff__field--${state}">
      <div class="people-diff__label">${renderLabel(field)}</div>
      <div class="people-diff__cell people-diff__cell--old">${parts.old}</div>
      <div class="people-diff__gutter">${parts.copy ?? ""}</div>
      <div class="people-diff__cell people-diff__cell--new">
        ${parts.new}
        ${parts.error
          ? html`<div class="people-diff__field-error">⚠ ${parts.error}</div>`
          : ""}
      </div>
    </div>
  `;
}

function renderOldText(text: string, state: string) {
  if (!text) return DASH;
  return state === "changed" || state === "cleared"
    ? html`<del>${text}</del>`
    : text;
}

// ── Paired fields ────────────────────────────────────────────────────────────
// Text, date and division all read `old → new` and differ only in the control on
// the new side. That control is passed in, so the surrounding rules — how a
// removed card reads, when the copy arrow shows, read-only falling back to text
// — are written once and cannot drift between field types.

function renderPairedField(
  field: FieldSpec,
  oldRecord: any,
  newRecord: any,
  save: Save,
  isReadOnly: boolean,
  renderNewSide: NewSideRenderer,
) {
  const oldValue = diffValue(oldRecord, field);
  // A removed card has no new record: treat its new value as empty so the field
  // reads as `cleared` (old struck → "—"), not `same`.
  const state = fieldDiffState(
    oldValue,
    newRecord ? diffValue(newRecord, field) : "",
    field.type,
  );
  const error = !isReadOnly && newRecord ? fieldError(field, newRecord) : null;
  const hasOld = String(oldValue ?? "").trim() !== "";
  return fieldRow(field, state, {
    old: renderOldText(oldRecord ? displayScalar(field, oldRecord) : "", state),
    copy: copyArrow(
      !isReadOnly && !!newRecord && hasOld && state !== "same",
      () => save(buildFieldUpdate(newRecord, field.key, oldValue)),
    ),
    error,
    new: !newRecord
      ? DASH
      : isReadOnly
        ? displayScalar(field, newRecord) || DASH
        : renderNewSide(field, newRecord, save, { state, error }),
  });
}

// ── Fields that assemble their own row ───────────────────────────────────────
// Multi, sources and photo each compute an old side the scaffold can't express:
// a per-value diff, a link list, an image.

function renderMultiField(
  field: FieldSpec,
  oldRecord: any,
  newRecord: any,
  save: Save,
  isReadOnly: boolean,
) {
  const oldValues = (diffValue(oldRecord, field) as string[]) ?? [];
  const newValues = (diffValue(newRecord, field) as string[]) ?? [];
  const oldSet = new Set(oldValues.map(normalizeMultiValue));
  const newSet = new Set(newValues.map(normalizeMultiValue));
  const setValues = (values: string[]) => save({ [field.key]: values });
  // Multi copy ADDS the old values that aren't already in new (union), rather
  // than replacing — so you don't lose what the scrape found.
  const oldOnly = oldValues.filter((v) => !newSet.has(normalizeMultiValue(v)));
  const state = multiValueState(oldValues, newValues);
  return fieldRow(field, state, {
    copy: copyArrow(!isReadOnly && !!newRecord && oldOnly.length > 0, () =>
      setValues([...newValues, ...oldOnly]),
    ),
    old: oldValues.length
      ? oldValues.map((value) => {
          const removed = !newSet.has(normalizeMultiValue(value));
          return html`<div
            class="people-diff__value ${removed
              ? "people-diff__value--removed"
              : ""}"
          >
            ${value}
          </div>`;
        })
      : DASH,
    new: !newRecord
      ? DASH
      : isReadOnly
        ? newValues.length
          ? newValues.map(
              (value) => html`<div class="people-diff__value">${value}</div>`,
            )
          : DASH
        : renderMultiNewSide(
            newValues,
            oldSet,
            setValues,
            field.label.toLowerCase(),
          ),
  });
}

function renderSourceUrlsField(
  field: FieldSpec,
  oldRecord: any,
  newRecord: any,
  save: Save,
  isReadOnly: boolean,
) {
  const oldValues = (diffValue(oldRecord, field) as string[]) ?? [];
  const newValues = (diffValue(newRecord, field) as string[]) ?? [];
  const setValues = (values: string[]) => save({ source_urls: values });
  // source_urls are documentation, not part of recordsDiffer — never accented.
  return fieldRow(field, "same", {
    old: oldValues.length ? sourceLinks(oldValues) : DASH,
    new: !newRecord
      ? DASH
      : isReadOnly
        ? newValues.length
          ? sourceLinks(newValues)
          : DASH
        : renderSourceUrlsNewSide(newValues, setValues),
  });
}

function renderImageField(
  field: FieldSpec,
  oldRecord: any,
  newRecord: any,
  save: Save,
  isReadOnly: boolean,
) {
  const state = fieldDiffState(
    oldRecord ? diffValue(oldRecord, field) : "",
    newRecord?.image ?? "",
    "image",
  );
  return fieldRow(field, state, {
    // Old side displays cdn_image (person-image's default); the new side aliases
    // the scraped `image` onto it — see renderPhotoNewSide.
    old: oldRecord
      ? html`<person-image .person=${oldRecord} size="2.75rem"></person-image>`
      : DASH,
    new: !newRecord ? DASH : renderPhotoNewSide(newRecord, save, isReadOnly),
  });
}

export function renderField(
  field: FieldSpec,
  oldRecord: any,
  newRecord: any,
  save: Save,
  isReadOnly: boolean,
  jurisdictionOcdid: string | null | undefined,
) {
  const paired = (renderNewSide: NewSideRenderer) =>
    renderPairedField(
      field,
      oldRecord,
      newRecord,
      save,
      isReadOnly,
      renderNewSide,
    );

  if (field.key === "office.division_ocdid")
    return paired((f, n, s) =>
      renderDivisionNewSide(f, n, s, jurisdictionOcdid),
    );
  if (field.key === "source_urls")
    return renderSourceUrlsField(field, oldRecord, newRecord, save, isReadOnly);
  if (field.type === "date") return paired(renderDateNewSide);
  if (field.type === "image")
    return renderImageField(field, oldRecord, newRecord, save, isReadOnly);
  if (field.type === "multi")
    return renderMultiField(field, oldRecord, newRecord, save, isReadOnly);
  return paired(renderScalarNewSide);
}
