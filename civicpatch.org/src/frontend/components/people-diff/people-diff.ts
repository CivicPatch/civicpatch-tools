import "./people-diff.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { computePeopleDiff } from "../../utils/diff-utils.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import "../person-image.js";
import {
  FIELD_SCHEMA,
  diffValue,
  fieldDiffState,
  fieldError,
  recordsDiffer,
  normalizeMultiValue,
  type FieldSpec,
} from "./diff-model.js";
import {
  parseDivision,
  jurisdictionToDivisionBase,
  DIVISION_AT_LARGE,
  DIVISION_OTHER,
} from "../edit-people/person-edit-utils.js";

const DASH = "—";

// A single named tab reused by every source-url link: first click opens it,
// later clicks re-land in the same tab instead of spawning new ones.
const SOURCE_LINK_TARGET = "civicpatch-source";

type FilterKey = "all" | "changed" | "added" | "removed" | "unchanged";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "changed", label: "Changed" },
  { key: "added", label: "New" },
  { key: "removed", label: "Removed" },
  { key: "unchanged", label: "Unchanged" },
];

interface PeopleDiffProps {
  existing: any[];
  currentPeople: any[];
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
  onAdd?: () => void;
  onResetPerson?: (id: string) => void;
  jurisdictionOcdid?: string | null;
  isReadOnly?: boolean;
}

type Save = (updates: Record<string, unknown>) => void;

// usePeopleState applies updates with a shallow merge, so `office` (a nested
// object) is replaced whole; every other field is a top-level value.
function buildFieldUpdate(person: any, key: string, value: unknown): Record<string, unknown> {
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

function displayScalar(field: FieldSpec, person: any): string {
  const value = diffValue(person, field);
  if (!value) return "";
  if (field.key === "office.division_ocdid") return divisionOcdidToFriendly(value as string) || String(value);
  return String(value);
}

// ── Shared row scaffold ──────────────────────────────────────────────────────
// Every field is `label | old | copy-gutter | new`. Each field type supplies
// only its old/new content (+ optional copy arrow + error); this owns the grid.

function renderLabel(field: FieldSpec) {
  return html`${field.label}${field.required ? html` <span class="people-diff__req">*</span>` : ""}`;
}

function copyArrow(show: boolean, onCopy: () => void) {
  return show
    ? html`<button class="people-diff__copy" title="copy old → new" @click=${onCopy}><i class="fa-solid fa-arrow-right"></i></button>`
    : "";
}

function fieldRow(field: FieldSpec, parts: { old: unknown; copy?: unknown; new: unknown; error?: string | null }) {
  return html`
    <div class="people-diff__field">
      <div class="people-diff__label">${renderLabel(field)}</div>
      <div class="people-diff__cell people-diff__cell--old">${parts.old}</div>
      <div class="people-diff__gutter">${parts.copy ?? ""}</div>
      <div class="people-diff__cell people-diff__cell--new">
        ${parts.new}
        ${parts.error ? html`<div class="people-diff__field-error">⚠ ${parts.error}</div>` : ""}
      </div>
    </div>
  `;
}

function renderOldText(text: string, state: string) {
  if (!text) return DASH;
  return state === "changed" || state === "cleared" ? html`<del>${text}</del>` : text;
}

// ── Field renderers ──────────────────────────────────────────────────────────

function renderScalarField(field: FieldSpec, oldRecord: any, newRecord: any, save: Save, isReadOnly: boolean) {
  const oldValue = diffValue(oldRecord, field);
  const state = newRecord ? fieldDiffState(oldValue, diffValue(newRecord, field), field.type) : "same";
  const error = !isReadOnly && newRecord ? fieldError(field, newRecord) : null;
  const hasOld = String(oldValue ?? "").trim() !== "";
  return fieldRow(field, {
    old: renderOldText(oldRecord ? displayScalar(field, oldRecord) : "", state),
    copy: copyArrow(!isReadOnly && !!newRecord && hasOld && state !== "same", () => save(buildFieldUpdate(newRecord, field.key, oldValue))),
    error,
    new: !newRecord
      ? DASH
      : isReadOnly
        ? displayScalar(field, newRecord) || DASH
        : html`<input
            class="people-diff__input people-diff__input--${state} ${error ? "people-diff__input--error" : ""}"
            .value=${displayScalar(field, newRecord)}
            @input=${(e: Event) => save(buildFieldUpdate(newRecord, field.key, (e.target as HTMLInputElement).value))}
          />`,
  });
}

function renderMultiNewSide(values: string[], oldSet: Set<string>, setValues: (v: string[]) => void, label: string) {
  return html`
    <div class="people-diff__multi">
      ${values.map((value, i) => {
        const added = !oldSet.has(normalizeMultiValue(value));
        return html`<div class="people-diff__multi-row">
          <input
            class="people-diff__input ${added ? "people-diff__input--added" : ""}"
            .value=${value}
            @input=${(e: Event) => setValues(values.map((v, j) => (j === i ? (e.target as HTMLInputElement).value : v)))}
          />
          <button class="people-diff__x" title="remove" @click=${() => setValues(values.filter((_, j) => j !== i))}><i class="fa-solid fa-xmark"></i></button>
        </div>`;
      })}
      <button class="people-diff__add" @click=${() => setValues([...values, ""])}>+ add ${label}</button>
    </div>
  `;
}

function renderMultiField(field: FieldSpec, oldRecord: any, newRecord: any, save: Save, isReadOnly: boolean) {
  const oldValues = (diffValue(oldRecord, field) as string[]) ?? [];
  const newValues = (diffValue(newRecord, field) as string[]) ?? [];
  const oldSet = new Set(oldValues.map(normalizeMultiValue));
  const newSet = new Set(newValues.map(normalizeMultiValue));
  const setValues = (values: string[]) => save({ [field.key]: values });
  // Multi copy ADDS the old values that aren't already in new (union), rather
  // than replacing — so you don't lose what the scrape found.
  const oldOnly = oldValues.filter((v) => !newSet.has(normalizeMultiValue(v)));
  return fieldRow(field, {
    copy: copyArrow(!isReadOnly && !!newRecord && oldOnly.length > 0, () => setValues([...newValues, ...oldOnly])),
    old: oldValues.length
      ? oldValues.map((value) => {
          const removed = !newSet.has(normalizeMultiValue(value));
          return html`<div class="people-diff__value ${removed ? "people-diff__value--removed" : ""}">${value}</div>`;
        })
      : DASH,
    new: !newRecord
      ? DASH
      : isReadOnly
        ? newValues.length
          ? newValues.map((value) => html`<div class="people-diff__value">${value}</div>`)
          : DASH
        : renderMultiNewSide(newValues, oldSet, setValues, field.label.toLowerCase()),
  });
}

function renderDivisionNewSide(field: FieldSpec, newRecord: any, save: Save, jurisdictionOcdid: string | null | undefined) {
  const newOcdid = diffValue(newRecord, field) as string | null | undefined;
  const division = parseDivision(newOcdid);
  const isOther = division.type === DIVISION_OTHER;
  const atLarge = division.type === DIVISION_AT_LARGE;
  const base = jurisdictionOcdid ? jurisdictionToDivisionBase(jurisdictionOcdid) : newOcdid ?? "";
  const rebuild = (type: string, value: string) =>
    type === DIVISION_AT_LARGE || type === DIVISION_OTHER ? base : `${base}/${type}:${value}`;
  return html`
    <div class="people-diff__division">
      <select class="people-diff__division-select" aria-label="Division type"
        @change=${(e: Event) => save(buildFieldUpdate(newRecord, field.key, rebuild((e.target as HTMLSelectElement).value, "")))}>
        ${isOther ? html`<option selected disabled>Custom: ${newOcdid}</option>` : ""}
        <option value=${DIVISION_AT_LARGE} ?selected=${atLarge}>At-large (no district)</option>
        <option value="council_district" ?selected=${division.type === "council_district"}>Council District</option>
        <option value="ward" ?selected=${division.type === "ward"}>Ward</option>
      </select>
      ${atLarge || isOther
        ? ""
        : html`<input class="people-diff__division-input" type="text" placeholder="Number" aria-label="Division number"
            .value=${division.value}
            @input=${(e: Event) => save(buildFieldUpdate(newRecord, field.key, rebuild(division.type, (e.target as HTMLInputElement).value)))} />`}
    </div>
  `;
}

function renderDivisionField(field: FieldSpec, oldRecord: any, newRecord: any, save: Save, isReadOnly: boolean, jurisdictionOcdid: string | null | undefined) {
  const state = newRecord ? fieldDiffState(diffValue(oldRecord, field), diffValue(newRecord, field), field.type) : "same";
  const error = !isReadOnly && newRecord ? fieldError(field, newRecord) : null;
  return fieldRow(field, {
    old: renderOldText(oldRecord ? displayScalar(field, oldRecord) : "", state),
    copy: copyArrow(!isReadOnly && !!newRecord && String(diffValue(oldRecord, field) ?? "").trim() !== "" && state !== "same", () => save(buildFieldUpdate(newRecord, field.key, diffValue(oldRecord, field)))),
    error,
    new: !newRecord
      ? DASH
      : isReadOnly
        ? displayScalar(field, newRecord) || DASH
        : renderDivisionNewSide(field, newRecord, save, jurisdictionOcdid),
  });
}

function sourceLinks(urls: string[]) {
  return html`<div class="people-diff__source-urls">
    ${urls.map((url) => html`<a class="people-diff__source-link" href=${ensureUrl(url)} target=${SOURCE_LINK_TARGET}>${url} <i class="fa-solid fa-arrow-up-right-from-square people-diff__source-icon"></i></a>`)}
  </div>`;
}

function renderSourceUrlsField(field: FieldSpec, oldRecord: any, newRecord: any, save: Save, isReadOnly: boolean) {
  const oldValues = (diffValue(oldRecord, field) as string[]) ?? [];
  const newValues = (diffValue(newRecord, field) as string[]) ?? [];
  const setValues = (values: string[]) => save({ source_urls: values });
  return fieldRow(field, {
    old: oldValues.length ? sourceLinks(oldValues) : DASH,
    new: !newRecord
      ? DASH
      : isReadOnly
        ? newValues.length ? sourceLinks(newValues) : DASH
        : html`<div class="people-diff__multi">
            ${newValues.map((value, i) => html`<div class="people-diff__multi-row">
              <input class="people-diff__input" .value=${value}
                @input=${(e: Event) => setValues(newValues.map((v, j) => (j === i ? (e.target as HTMLInputElement).value : v)))} />
              <a class="people-diff__source-link-btn" href=${ensureUrl(value)} target=${SOURCE_LINK_TARGET} title="open link"><i class="fa-solid fa-arrow-up-right-from-square"></i></a>
              <button class="people-diff__x" title="remove" @click=${() => setValues(newValues.filter((_, j) => j !== i))}><i class="fa-solid fa-xmark"></i></button>
            </div>`)}
            <button class="people-diff__add" @click=${() => setValues([...newValues, ""])}>+ add source url</button>
          </div>`,
  });
}

function renderImageField(field: FieldSpec, oldRecord: any, newRecord: any, save: Save, isReadOnly: boolean) {
  const hasNewImage = !!newRecord?.image;
  // Old side always displays cdn_image (person-image's default); the new side
  // always uses the scraped `image`, fed in as cdn_image so person-image shows it.
  const newPerson = newRecord && { ...newRecord, cdn_image: newRecord.image };
  return fieldRow(field, {
    old: oldRecord ? html`<person-image .person=${oldRecord} size="2.75rem"></person-image>` : DASH,
    new: !newRecord
      ? DASH
      : html`<div class="people-diff__photo">
          <person-image .person=${newPerson} size="2.75rem"></person-image>
          ${hasNewImage && !isReadOnly ? html`<button class="people-diff__photo-clear" @click=${() => save({ image: null, cdn_image: null })}>Remove photo</button>` : ""}
        </div>`,
  });
}

function renderField(field: FieldSpec, oldRecord: any, newRecord: any, save: Save, isReadOnly: boolean, jurisdictionOcdid: string | null | undefined) {
  if (field.key === "office.division_ocdid") return renderDivisionField(field, oldRecord, newRecord, save, isReadOnly, jurisdictionOcdid);
  if (field.key === "source_urls") return renderSourceUrlsField(field, oldRecord, newRecord, save, isReadOnly);
  if (field.type === "image") return renderImageField(field, oldRecord, newRecord, save, isReadOnly);
  if (field.type === "multi") return renderMultiField(field, oldRecord, newRecord, save, isReadOnly);
  return renderScalarField(field, oldRecord, newRecord, save, isReadOnly);
}

function renderRow(
  status: string,
  oldRecord: any,
  newRecord: any,
  onPersonSave: PeopleDiffProps["onPersonSave"],
  onResetPerson: PeopleDiffProps["onResetPerson"],
  isReadOnly: boolean,
  jurisdictionOcdid: string | null | undefined,
) {
  const name = newRecord?.name || oldRecord?.name || DASH;
  const save: Save = (updates) => onPersonSave(newRecord.id, updates);
  const isDirty = newRecord?._dirty;
  return html`
    <div class="people-diff__person people-diff__person--${status}">
      <div class="people-diff__person-header">
        <div class="people-diff__hdr-main">
          <span class="people-diff__status">${status}</span>
          <span class="people-diff__name">${name}</span>
        </div>
        <div class="people-diff__gutter">
          ${copyArrow(status === "changed" && !isReadOnly, () => save({ ...oldRecord, id: newRecord.id }))}
        </div>
        <div class="people-diff__row-actions">
          ${isDirty && !isReadOnly && onResetPerson
            ? html`<button class="people-diff__reset btn-sm" @click=${() => onResetPerson(newRecord.id)}>Reset</button>`
            : ""}
        </div>
      </div>
      <div class="people-diff__fields">
        ${FIELD_SCHEMA.map((field) => renderField(field, oldRecord, newRecord, save, isReadOnly, jurisdictionOcdid))}
      </div>
    </div>
  `;
}

function PeopleDiff({ existing, currentPeople, onPersonSave, onAdd, onResetPerson, jurisdictionOcdid, isReadOnly = false }: PeopleDiffProps) {
  const [activeFilter, setActiveFilter] = useState<FilterKey>("all");

  const olds = Array.isArray(existing) ? existing : [];
  const news = Array.isArray(currentPeople) ? currentPeople : [];
  const { diffEntries, unchangedEntries } = computePeopleDiff(olds, news, recordsDiffer);

  const counts: Record<FilterKey, number> = {
    all: diffEntries.length + unchangedEntries.length,
    changed: diffEntries.filter((e) => e.type === "changed").length,
    added: diffEntries.filter((e) => e.type === "added").length,
    removed: diffEntries.filter((e) => e.type === "removed").length,
    unchanged: unchangedEntries.length,
  };

  // Added people float to the top (a freshly-added blank lands there to fill in),
  // then changed, then removed. Stable sort keeps newest-added first.
  const TYPE_ORDER: Record<string, number> = { added: 0, changed: 1, removed: 2 };
  const matchesFilter = (type: string) => activeFilter === "all" || activeFilter === type;
  const visibleDiffs = diffEntries
    .filter((e) => matchesFilter(e.type))
    .sort((a, b) => (TYPE_ORDER[a.type] ?? 9) - (TYPE_ORDER[b.type] ?? 9));
  const visibleUnchanged = matchesFilter("unchanged") ? unchangedEntries : [];

  if (counts.all === 0) {
    return html`<div class="people-diff">
      <div class="people-diff__header"><div class="people-diff__header-title">Officials list diff</div></div>
      <p class="people-diff__empty">No people to review.</p>
    </div>`;
  }

  return html`
    <div class="people-diff">
      <div class="people-diff__header">
        <div class="people-diff__header-title-row">
          <div class="people-diff__header-title">Officials list diff</div>
          ${!isReadOnly && onAdd
            ? html`<button class="people-diff__add-person btn-sm" @click=${onAdd}>+ Add person</button>`
            : ""}
        </div>
        <div class="people-diff__count-chips">
          ${FILTERS.map(
            (f) => html`
              <button
                class="people-diff__chip people-diff__chip--${f.key} ${activeFilter === f.key ? "people-diff__chip--active" : ""}"
                @click=${() => setActiveFilter(f.key)}
              >
                ${f.label}
                ${counts[f.key] > 0 ? html`<span class="people-diff__chip-count">${counts[f.key]}</span>` : ""}
              </button>
            `,
          )}
        </div>
      </div>
      <div class="people-diff__legend">
        <span>Old</span>
        <span>New — editable</span>
      </div>
      <div class="people-diff__rows">
        ${visibleDiffs.map(({ type, person, from }) => renderRow(type, from, person, onPersonSave, onResetPerson, isReadOnly, jurisdictionOcdid))}
        ${visibleUnchanged.map(({ person, from }) => renderRow("unchanged", from, person, onPersonSave, onResetPerson, isReadOnly, jurisdictionOcdid))}
      </div>
    </div>
  `;
}

customElements.define("people-diff", component(PeopleDiff, { useShadowDOM: false }));
