// The editable control for one field, and nothing else. Nothing here knows that
// a diff has two sides — each control takes a single record and renders what the
// reviewer types into. That is what makes them reusable by the rail, the modal
// and (eventually) merge's N-candidate picker, which are not two-column layouts.
//
// Pairing a control with an old value is rail-field.ts's job, not theirs.

import { html, nothing } from "lit-html";
import { ref } from "lit-html/directives/ref.js";
import "./field-controls.css";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import { PERSON_LINK_TARGET, SOURCE_LINK_TARGET } from "../../utils/source-links.js";
import {
  diffValue,
  type FieldSpec,
  type PresentRecord,
  type ScalarDiffState,
} from "./field-model.js";
import {
  parseDivision,
  jurisdictionToDivisionBase,
  buildDivisionFromBase,
  parseDate,
  serializeDate,
  setDatePart,
  MONTHS,
  DAYS,
  padDatePart,
  DIVISION_AT_LARGE,
  DIVISION_OTHER,
  type DateParts,
  type DivisionType,
} from "../edit-people/person-edit-utils.js";

export type Save = (updates: Record<string, unknown>) => void;

// A callback ref, not a `Ref` object: only the template that renders a control
// knows when it exists, and the call is that signal.
export type FocusRef = (el?: Element) => void;

// Which field asked for focus, and the ref that takes it. The rail decides
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
  if (key.startsWith("office.")) {
    const subKey = key.split(".")[1];
    return { office: { ...(person?.office ?? {}), [subKey]: value } };
  }
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
  if (field.key === "office.division_ocdid")
    return divisionOcdidToFriendly(value as string) || String(value);
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
        aria-label="Year"
        .value=${parts.year}
        @input=${(e: Event) => setPart("year", inputValue(e))}
      />
      <select
        aria-label="Month"
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
        aria-label="Day"
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

export function renderDivisionNewSide(
  field: FieldSpec,
  newRecord: PresentRecord,
  save: Save,
  jurisdictionOcdid: string | null | undefined,
  focusRef: FocusRef | null,
) {
  const newOcdid = diffValue(newRecord, field) as string | null | undefined;
  const division = parseDivision(newOcdid, jurisdictionOcdid);
  const isOther = division.type === DIVISION_OTHER;
  const atLarge = division.type === DIVISION_AT_LARGE;
  // Without a jurisdiction there is no base to derive, so the person's existing
  // division stands in as one — an edit still appends its district segment.
  const base = jurisdictionOcdid
    ? jurisdictionToDivisionBase(jurisdictionOcdid)
    : (newOcdid ?? "");
  const rebuild = (type: DivisionType, value: string) =>
    buildDivisionFromBase(base, type, value);
  const preview = isOther
    ? (newOcdid ?? "")
    : rebuild(division.type, division.value);
  return html`
    <div class="field-control__division">
      <select
        ${attachFocus(focusRef)}
        class="field-control__division-select"
        aria-label="Division type"
        @change=${(e: Event) =>
          save(
            buildFieldUpdate(
              newRecord,
              field.key,
              rebuild(inputValue(e) as DivisionType, ""),
            ),
          )}
      >
        ${isOther
          ? html`<option value=${DIVISION_OTHER} disabled .selected=${true}>
              Custom: ${newOcdid}
            </option>`
          : ""}
        <option value=${DIVISION_AT_LARGE} .selected=${atLarge}>
          At-large (no district)
        </option>
        <option
          value="council_district"
          .selected=${division.type === "council_district"}
        >
          Council District
        </option>
        <option value="ward" .selected=${division.type === "ward"}>Ward</option>
      </select>
      ${atLarge || isOther
        ? ""
        : html`<input
            class="field-control__division-input"
            type="text"
            placeholder="Number"
            aria-label="Division number"
            .value=${division.value}
            @input=${(e: Event) =>
              save(
                buildFieldUpdate(
                  newRecord,
                  field.key,
                  rebuild(division.type, inputValue(e)),
                ),
              )}
          />`}
      <!-- Labelled, not bare: on its own line under the select, a raw OCD-ID
           reads as a stray string rather than as this control's output. -->
      <small class="field-control__division-preview">
        <span class="field-control__division-preview-label">saves as</span>
        ${preview}
      </small>
    </div>
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

export function renderSourceUrlsNewSide(
  values: string[],
  setValues: (v: string[]) => void,
  focusRef: FocusRef | null,
) {
  return html`<div class="field-control__multi">
    ${[...values, ""].map((value, i) => {
      const isDraft = i === values.length;
      return html`<div class="field-control__multi-row">
        <input
          ${attachFocus(i === 0 ? focusRef : null)}
          class="field-control__input"
          aria-label=${isDraft ? "Add source url" : nothing}
          placeholder=${isDraft ? "+ add source url" : nothing}
          .value=${value}
          @input=${(e: Event) => setValues(withValueAt(values, i, inputValue(e)))}
        />
        ${isDraft
          ? nothing
          : html`<a
                class="field-control__action"
                href=${ensureUrl(value)}
                target=${SOURCE_LINK_TARGET}
                title="open link"
                ><i class="fa-solid fa-arrow-up-right-from-square"></i
              ></a>
              <button
                class="field-control__action field-control__action--remove"
                title="remove"
                @click=${() => setValues(values.filter((_, j) => j !== i))}
              >
                <i class="fa-solid fa-xmark"></i>
              </button>`}
      </div>`;
    })}
  </div>`;
}

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
// A list of short strings is a list of chips, not a stack of full-width text
// boxes: three emails cost one line instead of three, and the field stops looking
// like a form the moment it holds more than one value.
//
// Provenance carries no words. `new` and `dropped` named the pipeline rather than
// the person, so state is the chip itself — an accent and a dot for a value this
// scrape brought in, dashed and struck for one the source stopped listing, whose
// only action is to come back. Tooltips carry the sentence for anyone who hovers.
//
// Provenance is passed in, not computed here: a merge picker (§21.5) derives it
// from N candidates rather than two sides, and this control should serve that
// unchanged.
export interface MultiRow {
  value: string;
  isNew: boolean;
}

// A chip is as wide as the value in it. Floored so an empty chip is still a
// target, capped so one long url cannot push the row off the card.
const CHIP_MIN_CHARS = 8;
const CHIP_MAX_CHARS = 38;

const chipSize = (value: string) =>
  Math.min(Math.max(value.length, CHIP_MIN_CHARS), CHIP_MAX_CHARS);

export function renderMultiList(
  rows: MultiRow[],
  dropped: string[],
  setValues: (values: string[]) => void,
  label: string,
  // Link fields get an open-in-new-tab affordance per row — a url you cannot
  // follow is a url you cannot check.
  areLinks = false,
  // `tel` for phones: the mobile keypad and autocomplete, nothing more. Validation
  // is the backend's (shared/schemas.py).
  inputType = "text",
  focusRef: FocusRef | null = null,
) {
  const values = rows.map((r) => r.value);
  return html`
    <div class="field-control__chips">
      ${[...rows, { value: "", isNew: false }].map((row, i) => {
        const isDraft = i === values.length;
        const hint = `+ add ${label}`;
        // The chip is the value and nothing else. Everything you can do to it
        // sits beside it, so one row shape serves every multi-value field.
        return html`<span class="field-control__chip-row">
          <span
            class="field-control__chip ${isDraft ? "field-control__chip--draft" : ""}"
            title=${row.isNew ? "Found by this scrape" : nothing}
          >
            <input
              ${attachFocus(i === 0 ? focusRef : null)}
              type=${inputType}
              size=${chipSize(isDraft ? hint : row.value)}
              aria-label=${isDraft ? `Add ${label}` : nothing}
              placeholder=${isDraft ? hint : nothing}
              .value=${row.value}
              @input=${(e: Event) => setValues(withValueAt(values, i, inputValue(e)))}
            />
          </span>
          ${areLinks && row.value.trim()
            ? html`<a
                class="field-control__action"
                href=${ensureUrl(row.value)}
                target=${PERSON_LINK_TARGET}
                title="Open link"
                ><i class="fa-solid fa-arrow-up-right-from-square"></i
              ></a>`
            : nothing}
          ${isDraft
            ? nothing
            : html`<button
                class="field-control__action field-control__action--remove"
                title="Remove"
                @click=${() => setValues(values.filter((_, j) => j !== i))}
              >
                <i class="fa-solid fa-xmark"></i>
              </button>`}
        </span>`;
      })}
      <!-- What the source stopped listing. Not an input: you are deciding about
           it, not editing it. -->
      ${dropped.map(
        (value) => html`<span class="field-control__chip-row">
          <span
            class="field-control__chip field-control__chip--gone"
            title="Removed by this scrape"
          >
            <s>${value}</s>
          </span>
          <button
            class="field-control__action field-control__action--restore"
            @click=${() => setValues([...values, value])}
          >
            <i class="fa-solid fa-rotate-left"></i> Put back
          </button>
        </span>`,
      )}
    </div>
  `;
}
