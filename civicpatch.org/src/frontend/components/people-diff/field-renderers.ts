import { html } from "lit-html";
import "../person-image.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import { SOURCE_LINK_TARGET } from "../../utils/source-links.js";
import {
  diffValue,
  fieldDiffState,
  fieldError,
  multiValueState,
  normalizeMultiValue,
  type FieldSpec,
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

export const DASH = "—";

export type Save = (updates: Record<string, unknown>) => void;

// usePeopleState applies updates with a shallow merge, so `office` (a nested
// object) is replaced whole; every other field is a top-level value.
function buildFieldUpdate(
  person: any,
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
function ensureUrl(value: string): string {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}

const inputValue = (e: Event) =>
  (e.target as HTMLInputElement | HTMLSelectElement).value;

function displayScalar(field: FieldSpec, person: any): string {
  const value = diffValue(person, field);
  if (!value) return "";
  if (field.key === "office.division_ocdid")
    return divisionOcdidToFriendly(value as string) || String(value);
  return String(value);
}

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

// The scaffold's own verdicts, for the controls that need to style themselves by
// them. Only the plain input does.
interface NewSideContext {
  state: ScalarDiffState;
  error: string | null;
}

type NewSideRenderer = (
  field: FieldSpec,
  newRecord: any,
  save: Save,
  context: NewSideContext,
) => unknown;

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

// ── Field renderers ──────────────────────────────────────────────────────────

function renderScalarNewSide(
  field: FieldSpec,
  newRecord: any,
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
function renderDateNewSide(field: FieldSpec, newRecord: any, save: Save) {
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


function renderMultiNewSide(
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
              setValues(
                values.map((v, j) =>
                  j === i ? (e.target as HTMLInputElement).value : v,
                ),
              )}
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

function renderDivisionNewSide(
  field: FieldSpec,
  newRecord: any,
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
              rebuild(
                (e.target as HTMLSelectElement).value as DivisionType,
                "",
              ),
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
                  rebuild(division.type, (e.target as HTMLInputElement).value),
                ),
              )}
          />`}
      <small class="people-diff__division-preview">${preview}</small>
    </div>
  `;
}


function sourceLinks(urls: string[]) {
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
        : html`<div class="people-diff__multi">
            ${newValues.map(
              (value, i) =>
                html`<div class="people-diff__multi-row">
                  <input
                    class="people-diff__input"
                    .value=${value}
                    @input=${(e: Event) =>
                      setValues(
                        newValues.map((v, j) =>
                          j === i ? (e.target as HTMLInputElement).value : v,
                        ),
                      )}
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
                    @click=${() =>
                      setValues(newValues.filter((_, j) => j !== i))}
                  >
                    <i class="fa-solid fa-xmark"></i>
                  </button>
                </div>`,
            )}
            <button
              class="people-diff__add"
              @click=${() => setValues([...newValues, ""])}
            >
              + add source url
            </button>
          </div>`,
  });
}

function renderImageField(
  field: FieldSpec,
  oldRecord: any,
  newRecord: any,
  save: Save,
  isReadOnly: boolean,
) {
  const hasNewImage = !!newRecord?.image;
  const state = fieldDiffState(
    oldRecord ? diffValue(oldRecord, field) : "",
    newRecord?.image ?? "",
    "image",
  );
  // Old side always displays cdn_image (person-image's default); the new side
  // always uses the scraped `image`, fed in as cdn_image so person-image shows it.
  const newPerson = newRecord && { ...newRecord, cdn_image: newRecord.image };
  return fieldRow(field, state, {
    old: oldRecord
      ? html`<person-image .person=${oldRecord} size="2.75rem"></person-image>`
      : DASH,
    new: !newRecord
      ? DASH
      : html`<div class="people-diff__photo">
          <person-image .person=${newPerson} size="2.75rem"></person-image>
          ${hasNewImage && !isReadOnly
            ? html`<button
                class="people-diff__photo-clear"
                @click=${() => save({ image: null, cdn_image: null })}
              >
                Remove photo
              </button>`
            : ""}
        </div>`,
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
    return paired((f, n, s) => renderDivisionNewSide(f, n, s, jurisdictionOcdid));
  if (field.key === "source_urls")
    return renderSourceUrlsField(field, oldRecord, newRecord, save, isReadOnly);
  if (field.type === "date") return paired(renderDateNewSide);
  if (field.type === "image")
    return renderImageField(field, oldRecord, newRecord, save, isReadOnly);
  if (field.type === "multi")
    return renderMultiField(field, oldRecord, newRecord, save, isReadOnly);
  return paired(renderScalarNewSide);
}
