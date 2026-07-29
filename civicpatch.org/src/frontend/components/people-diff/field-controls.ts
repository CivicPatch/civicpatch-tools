// The editable control for one field, and nothing else. Nothing here knows that
// a diff has two sides — each control takes a single record and renders what the
// reviewer types into. That is what makes them reusable by the rail, the modal
// and (eventually) merge's N-candidate picker, which are not two-column layouts.
//
// The `old | copy | new` assembly lives in field-renderers.ts.

import { html } from "lit-html";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import { SOURCE_LINK_TARGET } from "../../utils/source-links.js";
import {
  diffValue,
  normalizeMultiValue,
  type FieldSpec,
  type PresentRecord,
  type ScalarDiffState,
} from "./diff-model.js";
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
) {
  return html`<input
    class="people-diff__input people-diff__input--${state} ${error
      ? "people-diff__input--error"
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
) {
  const parts = parseDate(
    diffValue(newRecord, field) as string | null | undefined,
  );
  const setPart = (key: keyof DateParts, value: string) => {
    const next = setDatePart(parts, key, value);
    save(buildFieldUpdate(newRecord, field.key, serializeDate(next) || null));
  };
  return html`
    <div class="people-diff__date">
      <input
        class="people-diff__date-year"
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

export function renderMultiNewSide(
  values: string[],
  oldSet: Set<string>,
  setValues: (v: string[]) => void,
  label: string,
) {
  return html`
    <div class="people-diff__multi">
      ${values.map((value, i) => {
        const added = !oldSet.has(normalizeMultiValue(value));
        return html`<div class="people-diff__multi-row">
          <input
            class="people-diff__input ${added
              ? "people-diff__input--added"
              : ""}"
            .value=${value}
            @input=${(e: Event) =>
              setValues(values.map((v, j) => (j === i ? inputValue(e) : v)))}
          />
          <button
            class="people-diff__x"
            title="remove"
            @click=${() => setValues(values.filter((_, j) => j !== i))}
          >
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>`;
      })}
      <button
        class="people-diff__add"
        @click=${() => setValues([...values, ""])}
      >
        + add ${label}
      </button>
    </div>
  `;
}

export function renderDivisionNewSide(
  field: FieldSpec,
  newRecord: PresentRecord,
  save: Save,
  jurisdictionOcdid: string | null | undefined,
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
    <div class="people-diff__division">
      <select
        class="people-diff__division-select"
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
            class="people-diff__division-input"
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
      <small class="people-diff__division-preview">${preview}</small>
    </div>
  `;
}

export function renderSourceUrlsNewSide(
  values: string[],
  setValues: (v: string[]) => void,
) {
  return html`<div class="people-diff__multi">
    ${values.map(
      (value, i) =>
        html`<div class="people-diff__multi-row">
          <input
            class="people-diff__input"
            .value=${value}
            @input=${(e: Event) =>
              setValues(values.map((v, j) => (j === i ? inputValue(e) : v)))}
          />
          <a
            class="people-diff__source-link-btn"
            href=${ensureUrl(value)}
            target=${SOURCE_LINK_TARGET}
            title="open link"
            ><i class="fa-solid fa-arrow-up-right-from-square"></i
          ></a>
          <button
            class="people-diff__x"
            title="remove"
            @click=${() => setValues(values.filter((_, j) => j !== i))}
          >
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>`,
    )}
    <button class="people-diff__add" @click=${() => setValues([...values, ""])}>
      + add source url
    </button>
  </div>`;
}

export function sourceLinks(urls: string[]) {
  return html`<div class="people-diff__source-urls">
    ${urls.map(
      (url) =>
        html`<a
          class="people-diff__source-link"
          href=${ensureUrl(url)}
          target=${SOURCE_LINK_TARGET}
          >${url}
          <i
            class="fa-solid fa-arrow-up-right-from-square people-diff__source-icon"
          ></i
        ></a>`,
    )}
  </div>`;
}

// The scraped record carries `image`; person-image reads `cdn_image`, so the new
// side is shown by aliasing one onto the other.
export function renderPhotoNewSide(
  newRecord: PresentRecord,
  save: Save,
  isReadOnly: boolean,
) {
  return html`<div class="people-diff__photo">
    <person-image
      .person=${{ ...newRecord, cdn_image: newRecord.image }}
      size="2.75rem"
    ></person-image>
    ${newRecord.image && !isReadOnly
      ? html`<button
          class="people-diff__photo-clear"
          @click=${() => save({ image: null, cdn_image: null })}
        >
          Remove photo
        </button>`
      : ""}
  </div>`;
}
