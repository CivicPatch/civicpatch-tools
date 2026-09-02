// The card shell both Overview and Preview draw.
//
// Shared: the grid, the flush photo, name, post and division, and the metadata row
// beneath. Per view: what goes in that row — Overview puts status and field names
// there, Preview puts published values. If a change to one view's meta forces an
// edit here, the seam is in the wrong place.
//
// Interactivity is optional. Overview opens the editor, so its identity area is a
// button. Preview is a record to read and copy from, so it is plain selectable
// text — text inside a button is awkward to select, and there is nothing to open.

import { html, nothing } from "lit-html";
import "../person-image.js";
import "./person-row.css";
import { withDisplayImage } from "../fields/field-controls.js";
import { type DiffRecord } from "../fields/field-model.js";

export interface PersonRowProps {
  record: DiffRecord;
  name: string;
  subtitle: string;
  // Everything the row says, in one string: when the identity area is a button, a
  // screen reader gets this rather than its parts.
  ariaLabel?: string;
  // Absent means the row is not interactive.
  onOpen?: (() => void) | null;
  // Status class suffix, or none — Preview carries no diff vocabulary at all.
  modifier?: string | null;
  meta?: unknown;
}

export function renderPersonRow({
  record,
  name,
  subtitle,
  ariaLabel = "",
  onOpen = null,
  modifier = null,
  meta = nothing,
}: PersonRowProps) {
  const identity = onOpen
    ? html`<button class="review-row__open" aria-label=${ariaLabel} @click=${onOpen}>
        <span class="review-row__name">${name}</span>
        <span class="review-row__sub">${subtitle || nothing}</span>
      </button>`
    : html`<span class="review-row__open review-row__open--static">
        <span class="review-row__name">${name}</span>
        <span class="review-row__sub">${subtitle || nothing}</span>
      </span>`;

  return html`
    <div
      class="review-row ${modifier ? `review-row--${modifier}` : ""} ${onOpen
        ? ""
        : "review-row--static"}"
    >
      <span class="review-row__photo">
        <person-image
          .person=${withDisplayImage(record)}
          .size=${"6rem"}
        ></person-image>
      </span>
      ${identity}
      <span class="review-row__meta">${meta}</span>
      ${onOpen
        ? html`<i class="fa-solid fa-pen-to-square review-row__hint" aria-hidden="true"></i>`
        : nothing}
    </div>
  `;
}

/** The rows, in the container that lays them out.
 *
 * Callers used to assemble this themselves and a comment asked them to keep the pieces in
 * step — the grid class, the source map `renderValues` reads. Both callers already reduce
 * their own shape to `PersonRowProps`, so this takes it from there and the footgun is gone.
 */
export function renderPersonGrid(rows: PersonRowProps[]) {
  return html`
    <div class="review-preview__grid">${rows.map(renderPersonRow)}</div>
  `;
}
