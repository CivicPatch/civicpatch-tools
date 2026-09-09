
import { html, nothing } from "lit-html";
import "../person-image.js";
import "./person-row.css";
import { withDisplayImage } from "../fields/field-controls.js";
import { type DiffRecord } from "../fields/field-model.js";

export interface PersonRowProps {
  record: DiffRecord;
  name: string;
  subtitle: string;
  ariaLabel?: string;
  onOpen?: (() => void) | null;
  modifier?: string | null;
  meta?: unknown;
  isOpen?: boolean;
  controlsId?: string;
}

export function renderPersonRow({
  record,
  name,
  subtitle,
  ariaLabel = "",
  onOpen = null,
  modifier = null,
  meta = nothing,
  isOpen = false,
  controlsId,
}: PersonRowProps) {
  const identity = onOpen
    ? html`<button
        class="review-row__open"
        aria-label=${ariaLabel}
        aria-expanded=${isOpen}
        aria-controls=${controlsId ?? nothing}
        @click=${onOpen}
      >
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
        : "review-row--static"} ${isOpen ? "review-row--open" : ""}"
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
        ? html`<i class="fa-solid fa-chevron-down review-row__hint" aria-hidden="true"></i>`
        : nothing}
    </div>
  `;
}

export function renderPersonGrid(rows: PersonRowProps[]) {
  return html`
    <div class="review-preview__grid">${rows.map(renderPersonRow)}</div>
  `;
}
