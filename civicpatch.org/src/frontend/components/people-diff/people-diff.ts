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
  recordsDiffer,
  normalizeMultiValue,
  type FieldSpec,
} from "./diff-model.js";

const DASH = "—";

interface PeopleDiffProps {
  existing: any[];
  currentPeople: any[];
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
  isReadOnly?: boolean;
}

// usePeopleState applies updates with a shallow merge, so `office` (a nested
// object) is replaced whole; every other field is a top-level value.
function buildFieldUpdate(person: any, key: string, value: unknown): Record<string, unknown> {
  if (key.startsWith("office.")) {
    const subKey = key.split(".")[1];
    return { office: { ...(person?.office ?? {}), [subKey]: value } };
  }
  return { [key]: value };
}

function displayScalar(field: FieldSpec, person: any): string {
  const value = diffValue(person, field);
  if (!value) return "";
  if (field.key === "office.division_ocdid") return divisionOcdidToFriendly(value as string) || String(value);
  return String(value);
}

function renderLabel(field: FieldSpec) {
  return html`${field.label}${field.required ? html` <span class="people-diff__req">*</span>` : ""}`;
}

function renderOld(text: string, state: string) {
  if (!text) return DASH;
  return state === "changed" || state === "cleared" ? html`<del>${text}</del>` : text;
}

function renderScalarField(field: FieldSpec, oldRecord: any, newRecord: any, save: (updates: Record<string, unknown>) => void, isReadOnly: boolean) {
  const oldValue = diffValue(oldRecord, field);
  const state = newRecord ? fieldDiffState(oldValue, diffValue(newRecord, field), field.type) : "same";
  const canCopy = !isReadOnly && !!newRecord && !!oldRecord && state === "changed";
  return html`
    <div class="people-diff__field">
      <div class="people-diff__label">${renderLabel(field)}</div>
      <div class="people-diff__cell people-diff__cell--old">${renderOld(oldRecord ? displayScalar(field, oldRecord) : "", state)}</div>
      <div class="people-diff__gutter">
        ${canCopy ? html`<button class="people-diff__copy" title="copy old → new" @click=${() => save(buildFieldUpdate(newRecord, field.key, oldValue))}>→</button>` : ""}
      </div>
      <div class="people-diff__cell people-diff__cell--new">
        ${!newRecord
          ? DASH
          : isReadOnly
            ? displayScalar(field, newRecord) || DASH
            : html`<input
                class="people-diff__input people-diff__input--${state}"
                .value=${displayScalar(field, newRecord)}
                @input=${(e: Event) => save(buildFieldUpdate(newRecord, field.key, (e.target as HTMLInputElement).value))}
              />`}
      </div>
    </div>
  `;
}

function renderMultiField(field: FieldSpec, oldRecord: any, newRecord: any, save: (updates: Record<string, unknown>) => void, isReadOnly: boolean) {
  const oldValues = (diffValue(oldRecord, field) as string[]) ?? [];
  const newValues = (diffValue(newRecord, field) as string[]) ?? [];
  const oldSet = new Set(oldValues.map(normalizeMultiValue));
  const newSet = new Set(newValues.map(normalizeMultiValue));
  const setValues = (values: string[]) => save({ [field.key]: values });

  return html`
    <div class="people-diff__field">
      <div class="people-diff__label">${renderLabel(field)}</div>
      <div class="people-diff__cell people-diff__cell--old">
        ${oldValues.length
          ? oldValues.map((value) => {
              const removed = !newSet.has(normalizeMultiValue(value));
              return html`<div class="people-diff__value ${removed ? "people-diff__value--removed" : ""}">${value}</div>`;
            })
          : DASH}
      </div>
      <div class="people-diff__gutter"></div>
      <div class="people-diff__cell people-diff__cell--new">
        ${!newRecord
          ? DASH
          : isReadOnly
            ? newValues.length
              ? newValues.map((value) => html`<div class="people-diff__value">${value}</div>`)
              : DASH
            : html`<div class="people-diff__multi">
                ${newValues.map((value, i) => {
                  const added = !oldSet.has(normalizeMultiValue(value));
                  return html`<div class="people-diff__multi-row">
                    <input
                      class="people-diff__input ${added ? "people-diff__input--added" : ""}"
                      .value=${value}
                      @input=${(e: Event) => setValues(newValues.map((v, j) => (j === i ? (e.target as HTMLInputElement).value : v)))}
                    />
                    <button class="people-diff__x" title="remove" @click=${() => setValues(newValues.filter((_, j) => j !== i))}>×</button>
                  </div>`;
                })}
                <button class="people-diff__add" @click=${() => setValues([...newValues, ""])}>+ add ${field.label.toLowerCase()}</button>
              </div>`}
      </div>
    </div>
  `;
}

// Read-only ports (made editable in a later 3c step).
function renderDivisionField(field: FieldSpec, oldRecord: any, newRecord: any) {
  const state = newRecord ? fieldDiffState(diffValue(oldRecord, field), diffValue(newRecord, field), field.type) : "same";
  return html`
    <div class="people-diff__field">
      <div class="people-diff__label">${renderLabel(field)}</div>
      <div class="people-diff__cell people-diff__cell--old">${renderOld(oldRecord ? displayScalar(field, oldRecord) : "", state)}</div>
      <div class="people-diff__gutter"></div>
      <div class="people-diff__cell people-diff__cell--new">${newRecord ? displayScalar(field, newRecord) || DASH : DASH}</div>
    </div>
  `;
}

function renderImageField(field: FieldSpec, oldRecord: any, newRecord: any) {
  const state = newRecord ? fieldDiffState(diffValue(oldRecord, field), diffValue(newRecord, field), field.type) : "same";
  return html`
    <div class="people-diff__field">
      <div class="people-diff__label">${renderLabel(field)}</div>
      <div class="people-diff__cell people-diff__cell--old">${oldRecord ? html`<person-image .person=${oldRecord}></person-image>` : DASH}</div>
      <div class="people-diff__gutter"></div>
      <div class="people-diff__cell people-diff__cell--new people-diff__cell--${state}">${newRecord ? html`<person-image .person=${newRecord}></person-image>` : DASH}</div>
    </div>
  `;
}

function renderField(field: FieldSpec, oldRecord: any, newRecord: any, save: (updates: Record<string, unknown>) => void, isReadOnly: boolean) {
  if (field.key === "office.division_ocdid") return renderDivisionField(field, oldRecord, newRecord);
  if (field.type === "image") return renderImageField(field, oldRecord, newRecord);
  if (field.type === "multi") return renderMultiField(field, oldRecord, newRecord, save, isReadOnly);
  return renderScalarField(field, oldRecord, newRecord, save, isReadOnly);
}

function renderRow(status: string, oldRecord: any, newRecord: any, onPersonSave: PeopleDiffProps["onPersonSave"], isReadOnly: boolean) {
  const name = newRecord?.name || oldRecord?.name || DASH;
  const save = (updates: Record<string, unknown>) => onPersonSave(newRecord.id, updates);
  return html`
    <div class="people-diff__person people-diff__person--${status}">
      <div class="people-diff__person-header">
        <div class="people-diff__hdr-main">
          <span class="people-diff__status">${status}</span>
          <span class="people-diff__name">${name}</span>
        </div>
        <div class="people-diff__gutter">
          ${status === "changed" && !isReadOnly
            ? html`<button class="people-diff__copy" title="copy all old → new" @click=${() => save({ ...oldRecord, id: newRecord.id })}>→</button>`
            : ""}
        </div>
        <div class="people-diff__row-actions"></div>
      </div>
      <div class="people-diff__fields">
        ${FIELD_SCHEMA.map((field) => renderField(field, oldRecord, newRecord, save, isReadOnly))}
      </div>
    </div>
  `;
}

function PeopleDiff({ existing, currentPeople, onPersonSave, isReadOnly = false }: PeopleDiffProps) {
  const [showUnchanged, setShowUnchanged] = useState(false);

  const olds = Array.isArray(existing) ? existing : [];
  const news = Array.isArray(currentPeople) ? currentPeople : [];
  const { diffEntries, unchangedEntries } = computePeopleDiff(olds, news, recordsDiffer);

  return html`
    <div class="people-diff">
      <div class="people-diff__legend">
        <span>Old</span>
        <span>New — editable</span>
        ${unchangedEntries.length
          ? html`<button class="people-diff__toggle btn-sm" @click=${() => setShowUnchanged(!showUnchanged)}>
              ${showUnchanged ? "Hide" : `Show ${unchangedEntries.length}`} unchanged
            </button>`
          : ""}
      </div>
      <div class="people-diff__rows">
        ${diffEntries.map(({ type, person, from }) => renderRow(type, from, person, onPersonSave, isReadOnly))}
        ${showUnchanged ? unchangedEntries.map(({ person, from }) => renderRow("unchanged", from, person, onPersonSave, isReadOnly)) : ""}
      </div>
    </div>
  `;
}

customElements.define("people-diff", component(PeopleDiff, { useShadowDOM: false }));
