import { html } from "lit-html";
import { FIELD_LABELS, LEVEL_LABELS } from "./labels.js";
import type { FieldComparison, RowWarning, UploadedRow } from "./types.js";

const SIDE_UPLOADED = "uploaded";
const SIDE_CIVICPATCH = "civicpatch";
type Side = typeof SIDE_UPLOADED | typeof SIDE_CIVICPATCH;

/** One side's values, each tinted when the other side does not have it. */
export function valueChips(comparison: FieldComparison, side: Side) {
  const own = side === SIDE_UPLOADED ? comparison.uploaded : comparison.civicpatch;
  const other = new Set(side === SIDE_UPLOADED ? comparison.civicpatch : comparison.uploaded);
  return own.map(
    (value) =>
      html`<span class="rc-value ${other.has(value) ? "rc-value--shared" : `rc-value--${side}-only`}"
        >${value}</span
      >`,
  );
}

export const uploadedChips = (comparison: FieldComparison) => valueChips(comparison, SIDE_UPLOADED);
export const civicpatchChips = (comparison: FieldComparison) => valueChips(comparison, SIDE_CIVICPATCH);

export function valueLegend() {
  return html`<p class="rc-value-legend">
    <span class="rc-value rc-value--shared">on both sides</span>
    <span class="rc-value rc-value--uploaded-only">only in uploaded data</span>
    <span class="rc-value rc-value--civicpatch-only">only in civicpatch</span>
  </p>`;
}

export function levelChip(comparison: FieldComparison | undefined) {
  if (!comparison) return null;
  return html`<span class="rc-level rc-level--${comparison.level}">${LEVEL_LABELS[comparison.level] ?? comparison.level}</span>`;
}

/** "row 847", opening the row as it was uploaded on hover and on keyboard focus. */
export function rowRef(row: UploadedRow) {
  const fields = Object.entries(row).filter(([key]) => key !== "not_compared" && key !== "source_row");
  return html`<span class="rc-row-ref" tabindex="0">
    row ${row.source_row}
    <span class="rc-row-ref__popup" role="tooltip">
      <b>Row ${row.source_row} as uploaded</b>
      ${fields.map(([key, value]) => html`<span>${key}: ${formatValue(value)}</span>`)}
      ${Object.entries(row.not_compared).map(
        ([key, value]) => html`<span class="rc-row-ref__extra">${key}: ${formatValue(value)} (not compared)</span>`,
      )}
    </span>
  </span>`;
}

export function warningList(warnings: RowWarning[]) {
  if (!warnings.length) return null;
  return html`<ul class="rc-warnings">
    ${warnings.map((warning) => html`<li>⚠ ${warning.message}</li>`)}
  </ul>`;
}

export function columnNote(field: keyof typeof FIELD_LABELS, sourceColumns: Record<string, string[]>) {
  const columns = sourceColumns[field];
  return columns?.length ? html`<span class="rc-source">from ${columns.join(", ")}</span>` : null;
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  return value == null ? "" : String(value);
}
