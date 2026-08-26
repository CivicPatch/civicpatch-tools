// The editable control for one field, and nothing else. Nothing here knows that
// a diff has two sides — each control takes a single record and renders what the
// reviewer types into. That is what makes them reusable by the editor, the modal
// and (eventually) merge's N-candidate picker, which are not two-column layouts.
//
// Pairing a control with an old value is editor-field.ts's job, not theirs.

import { html, nothing } from "lit-html";
import { ref } from "lit-html/directives/ref.js";
import "./field-controls.css";
import { DERIVED_POST } from "../posts-list/posts-model.js";
import type { OfficeOption } from "../posts-list/posts-model.js";
import {
  PERSON_LINK_TARGET,
  SOURCE_LINK_TARGET,
} from "../../utils/source-links.js";
import {
  diffValue,
  type FieldSpec,
  type PresentRecord,
  type ScalarDiffState,
} from "./field-model.js";
import {
  parseDate,
  serializeDate,
  setDatePart,
  MONTHS,
  DAYS,
  padDatePart,
  type DateParts,
} from "../edit-people/person-edit-utils.js";

export type Save = (updates: Record<string, unknown>) => void;

// A callback ref, not a `Ref` object: only the template that renders a control
// knows when it exists, and the call is that signal.
export type FocusRef = (el?: Element) => void;

// Which field asked for focus, and the ref that takes it. The editor decides
// which row it lands on; the control decides which of its elements holds it.
export interface FieldFocus {
  key: string;
  attach: FocusRef;
}

// `nothing` in an element position is a no-op, so a control that was not asked
// for gets no ref at all.
export const attachFocus = (focusRef: FocusRef | null) =>
  focusRef ? ref(focusRef) : nothing;

// Verdicts the surrounding row already computed, for controls that style
// themselves by them. Only the plain input does.
export interface NewSideContext {
  state: ScalarDiffState;
  error: string | null;
}

export type NewSideRenderer = (
  field: FieldSpec,
  newRecord: PresentRecord,
  save: Save,
  context: NewSideContext,
) => unknown;

// ── Shared helpers ───────────────────────────────────────────────────────────

// usePeopleState applies updates with a shallow merge, so `office` (a nested
// object) is replaced whole; every other field is a top-level value.
export function buildFieldUpdate(
  person: PresentRecord,
  key: string,
  value: unknown,
): Record<string, unknown> {
  return { [key]: value };
}

// A bare "nh.gov/x" with no protocol is a *relative* href — it would navigate
// the review tab (losing edits). Force an absolute URL so target=_blank works.
export function ensureUrl(value: string): string {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}

export const inputValue = (e: Event) =>
  (e.target as HTMLInputElement | HTMLSelectElement).value;

export function displayScalar(field: FieldSpec, person: PresentRecord): string {
  const value = diffValue(person, field);
  if (!value) return "";
  return String(value);
}

// ── Controls ─────────────────────────────────────────────────────────────────

export function renderScalarNewSide(
  field: FieldSpec,
  newRecord: PresentRecord,
  save: Save,
  { state, error }: NewSideContext,
  focusRef: FocusRef | null,
) {
  return html`<input
    ${attachFocus(focusRef)}
    aria-label=${field.label}
    class="field-control__input field-control__input--${state} ${error
      ? "field-control__input--error"
      : ""}"
    .value=${displayScalar(field, newRecord)}
    @input=${(e: Event) =>
      save(buildFieldUpdate(newRecord, field.key, inputValue(e)))}
  />`;
}

// Partial dates are the majority of this data, so the new side is a Year box
// plus optional Month/Day selects rather than free text validated after the
// fact. Day is disabled until a month exists; clearing the month clears it.
//
// Selection binds `.selected` (the live property) on each <option>. Not
// `?selected` — that sets the attribute, which reflects `defaultSelected` and so
// stops tracking once the control is dirty. And not `.value` on the <select>:
// lit commits parts in template order, so it would run before the dynamic
// options exist and leave selectedIndex at -1 on first render.
export function renderDateNewSide(
  field: FieldSpec,
  newRecord: PresentRecord,
  save: Save,
  focusRef: FocusRef | null,
) {
  const parts = parseDate(
    diffValue(newRecord, field) as string | null | undefined,
  );
  const setPart = (key: keyof DateParts, value: string) => {
    const next = setDatePart(parts, key, value);
    save(buildFieldUpdate(newRecord, field.key, serializeDate(next) || null));
  };
  return html`
    <div class="field-control__date">
      <input
        ${attachFocus(focusRef)}
        class="field-control__date-year"
        type="number"
        min="1900"
        max="2100"
        placeholder="Year"
        aria-label=${`${field.label} year`}
        .value=${parts.year}
        @input=${(e: Event) => setPart("year", inputValue(e))}
      />
      <select
        aria-label=${`${field.label} month`}
        ?disabled=${!parts.year}
        @change=${(e: Event) => setPart("month", inputValue(e))}
      >
        <option value="" .selected=${!parts.month}>—</option>
        ${MONTHS.map(
          (name, i) =>
            html` <option
              value=${padDatePart(i + 1)}
              .selected=${padDatePart(i + 1) === parts.month}
            >
              ${name}
            </option>`,
        )}
      </select>
      <select
        aria-label=${`${field.label} day`}
        ?disabled=${!parts.month}
        @change=${(e: Event) => setPart("day", inputValue(e))}
      >
        <option value="" .selected=${!parts.day}>—</option>
        <!-- Without a month the select is disabled and its 31 options are never
             seen, so don't build them. setDatePart clears the day whenever the
             month clears, so there is never a day to lose here. -->
        ${parts.month
          ? DAYS.map(
              (day) =>
                html` <option value=${day} .selected=${day === parts.day}>
                  ${Number(day)}
                </option>`,
            )
          : ""}
      </select>
    </div>
  `;
}

// Posts are picked, never typed. A typed office is text the publish parser has to re-read,
// which is where the role and division guessing goes wrong.
//
// The written value is `post_id` — the decision itself. `labels` stay exactly as the source
// said them, because a pick says where someone serves, not what the page called them, and the
// membership is derived from the chosen post.
export function renderOfficeNewSide(
  field: FieldSpec,
  newRecord: PresentRecord,
  save: Save,
  options: OfficeOption[],
  focusRef: FocusRef | null,
) {
  const current = (diffValue(newRecord, field) as string | null) ?? "";
  // Nothing picked: the post is still whatever the labels derive to, which is the normal
  // state for a scrape nobody has corrected.
  const DERIVED = "";
  return html`
    <select
      ${attachFocus(focusRef)}
      class="field-control__office"
      aria-label=${field.label}
      @change=${(e: Event) => save({ post_id: inputValue(e) || null })}
    >
      <option value=${DERIVED} .selected=${!current}>${DERIVED_POST}</option>
      ${options.map(
        (option) =>
          html`<option
            value=${option.post_id}
            .selected=${option.post_id === current}
          >
            ${option.text}
          </option>`,
      )}
    </select>
  `;
}

// Every multi-value list renders one more row than it holds, and that trailing
// empty row is how a value gets added — so there is no button, and nothing to
// focus that does not exist yet. Writing at index === length appends, which is
// what turns the empty row into a real value on its first keystroke.
const withValueAt = (values: string[], i: number, value: string) => {
  const next = [...values];
  next[i] = value;
  return next;
};

export function sourceLinks(urls: string[]) {
  return html`<div class="field-control__source-urls">
    ${urls.map(
      (url) =>
        html`<a
          class="field-control__source-link"
          href=${ensureUrl(url)}
          target=${SOURCE_LINK_TARGET}
          >${url}
          <i
            class="fa-solid fa-arrow-up-right-from-square field-control__source-icon"
          ></i
        ></a>`,
    )}
  </div>`;
}

// person-image reads `cdn_image`, but a freshly scraped record only carries
// `image` — so anything showing a person's photo has to resolve the effective
// one first, or a scraped photo silently falls back to initials.
export const withDisplayImage = (person: PresentRecord) => ({
  ...person,
  cdn_image: person?.cdn_image || person?.image,
});

export function renderPhotoNewSide(
  newRecord: PresentRecord,
  save: Save,
  isReadOnly: boolean,
) {
  return html`<div class="field-control__photo">
    <person-image
      .person=${withDisplayImage(newRecord)}
      .size=${"2.75rem"}
    ></person-image>
    ${newRecord.image && !isReadOnly
      ? html`<button
          class="field-control__photo-clear"
          @click=${() => save({ image: null, cdn_image: null })}
        >
          Remove photo
        </button>`
      : ""}
  </div>`;
}

// ── Multi-value, as chips (§5.2) ─────────────────────────────────────────────
//
// Emails and phones are *sets*, and `old → new` is a pairing — there is nothing
// to pair, because multiValueDiff normalises and compares as sets by design. So
// the published list is the only list.
//
// One row per value, at full width. Values that are chips elsewhere are a
// stack here because urls are values too, and a control sized to its content
// truncates exactly the field most in need of being read in full.
//
// Provenance carries no words. `new` and `dropped` named the pipeline rather than
// the person, so state is the row itself — struck and dashed for a value the
// source stopped listing, whose only action is to come back. Tooltips carry the
// sentence for anyone who hovers.
//
// Provenance is passed in, not computed here: a merge picker (§21.5) derives it
// from N candidates rather than two sides, and this control should serve that
// unchanged.
export interface MultiRow {
  value: string;
  isNew: boolean;
  // Checked outside, like provenance — the control renders the verdict rather
  // than deciding it, so a merge picker can pass its own.
  isInvalid: boolean;
}

export interface MultiListProps {
  rows: MultiRow[];
  // Values the source stopped listing. Empty for fields that are never compared.
  dropped: string[];
  setValues: (values: string[]) => void;
  // Names the trailing empty row: "+ add email".
  label: string;
  // Non-null makes every row followable — a url you cannot follow is a url you
  // cannot check. Which window it opens in is the caller's: source links and
  // person links deliberately do not share one.
  linkTarget: string | null;
  // `tel` for phones: the mobile keypad and autocomplete, nothing more.
  // Validation is the backend's (shared/schemas.py).
  inputType: string;
  focusRef: FocusRef | null;
}

// Named after the value they act on, not after themselves: a card holds several
// of each, and "Remove" three times over says nothing about which. `title` stays
// for the pointer tooltip — as an accessible name it is too weak to rely on,
// since it never surfaces on touch.
const renderLinkAction = (value: string, target: string) =>
  html`<a
    class="field-control__action"
    href=${ensureUrl(value)}
    target=${target}
    aria-label=${`Open ${value}`}
    title="Open link"
    ><i class="fa-solid fa-arrow-up-right-from-square"></i
  ></a>`;

const renderRemoveAction = (value: string, remove: () => void) =>
  html`<button
    class="field-control__action field-control__action--remove"
    aria-label=${`Remove ${value}`}
    title="Remove"
    @click=${remove}
  >
    <i class="fa-solid fa-xmark"></i>
  </button>`;

// An action a row does not have still holds its place, so every input in a
// field is one width — otherwise the trailing empty row runs wider than the
// values above it, which reads as a different kind of control.
const ACTION_SPACER = html`<span
  class="field-control__action-spacer"
  aria-hidden="true"
></span>`;

// Shown, not edited: you are deciding about it, not changing it. `--cleared` is
// the same language a scalar field uses when the scrape emptied it.
const renderDroppedRow = (value: string, restore: () => void) =>
  html`<div class="field-control__multi-row">
    <span
      class="field-control__input field-control__input--cleared"
      title="Removed by this scrape"
      ><s>${value}</s></span
    >
    <button
      class="field-control__action field-control__action--restore"
      aria-label=${`Put back ${value}`}
      @click=${restore}
    >
      <i class="fa-solid fa-rotate-left"></i> Put back
    </button>
  </div>`;

export function renderMultiList(props: MultiListProps) {
  const { rows, dropped, setValues, label, linkTarget, inputType, focusRef } =
    props;
  const values = rows.map((row) => row.value);
  return html`
    <div class="field-control__multi">
      ${[...rows, { value: "", isNew: false, isInvalid: false }].map(
        (row, i) => {
          const isDraft = i === values.length;
          return html`<div class="field-control__multi-row">
            <input
              ${attachFocus(i === 0 ? focusRef : null)}
              class="field-control__input ${isDraft
                ? "field-control__input--draft"
                : ""} ${row.isInvalid ? "field-control__input--error" : ""}"
              type=${inputType}
              title=${row.isNew ? "Found by this scrape" : nothing}
              aria-label=${isDraft ? `Add ${label}` : `${label} ${i + 1}`}
              placeholder=${isDraft ? `+ add ${label}` : nothing}
              .value=${row.value}
              @input=${(e: Event) =>
                setValues(withValueAt(values, i, inputValue(e)))}
            />
            ${!linkTarget
              ? nothing
              : isDraft || !row.value.trim()
                ? ACTION_SPACER
                : renderLinkAction(row.value, linkTarget)}
            ${isDraft
              ? ACTION_SPACER
              : renderRemoveAction(row.value, () =>
                  setValues(values.filter((_, j) => j !== i)),
                )}
          </div>`;
        },
      )}
      ${dropped.map((value) =>
        renderDroppedRow(value, () => setValues([...values, value])),
      )}
    </div>
  `;
}
