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
  data: { existing: any[]; proposed: any[] };
}

function scalarText(field: FieldSpec, person: any): string {
  const value = diffValue(person, field);
  if (!value) return "";
  if (field.key === "office.division_ocdid") {
    return divisionOcdidToFriendly(value as string) || String(value);
  }
  return String(value);
}

function renderScalarField(field: FieldSpec, oldRecord: any, newRecord: any) {
  const state = fieldDiffState(diffValue(oldRecord, field), diffValue(newRecord, field), field.type);
  const oldText = scalarText(field, oldRecord);
  const newText = scalarText(field, newRecord);
  return html`
    <div class="people-diff__field">
      <div class="people-diff__label">${field.label}</div>
      <div class="people-diff__cell people-diff__cell--old">${oldText || DASH}</div>
      <div class="people-diff__cell people-diff__cell--new people-diff__cell--${state}">${newText || DASH}</div>
    </div>
  `;
}

function renderMultiField(field: FieldSpec, oldRecord: any, newRecord: any) {
  const oldValues = (diffValue(oldRecord, field) as string[]) ?? [];
  const newValues = (diffValue(newRecord, field) as string[]) ?? [];
  const oldSet = new Set(oldValues.map(normalizeMultiValue));
  const newSet = new Set(newValues.map(normalizeMultiValue));

  return html`
    <div class="people-diff__field">
      <div class="people-diff__label">${field.label}</div>
      <div class="people-diff__cell people-diff__cell--old">
        ${oldValues.length
          ? oldValues.map((value) => {
              const removed = !newSet.has(normalizeMultiValue(value));
              return html`<div class="people-diff__value ${removed ? "people-diff__value--removed" : ""}">${value}</div>`;
            })
          : DASH}
      </div>
      <div class="people-diff__cell people-diff__cell--new">
        ${newValues.length
          ? newValues.map((value) => {
              const added = !oldSet.has(normalizeMultiValue(value));
              return html`<div class="people-diff__value ${added ? "people-diff__value--added" : ""}">${value}</div>`;
            })
          : DASH}
      </div>
    </div>
  `;
}

function renderImageField(field: FieldSpec, oldRecord: any, newRecord: any) {
  const state = fieldDiffState(diffValue(oldRecord, field), diffValue(newRecord, field), field.type);
  return html`
    <div class="people-diff__field">
      <div class="people-diff__label">${field.label}</div>
      <div class="people-diff__cell people-diff__cell--old">
        ${oldRecord ? html`<person-image .person=${oldRecord}></person-image>` : DASH}
      </div>
      <div class="people-diff__cell people-diff__cell--new people-diff__cell--${state}">
        ${newRecord ? html`<person-image .person=${newRecord}></person-image>` : DASH}
      </div>
    </div>
  `;
}

function renderField(field: FieldSpec, oldRecord: any, newRecord: any) {
  if (field.type === "multi") return renderMultiField(field, oldRecord, newRecord);
  if (field.type === "image") return renderImageField(field, oldRecord, newRecord);
  return renderScalarField(field, oldRecord, newRecord);
}

function renderRow(status: string, oldRecord: any, newRecord: any) {
  const name = newRecord?.name || oldRecord?.name || DASH;
  return html`
    <div class="people-diff__person people-diff__person--${status}">
      <div class="people-diff__person-header">
        <span class="people-diff__status">${status}</span>
        <span class="people-diff__name">${name}</span>
      </div>
      <div class="people-diff__fields">
        ${FIELD_SCHEMA.map((field) => renderField(field, oldRecord, newRecord))}
      </div>
    </div>
  `;
}

function PeopleDiff({ data }: PeopleDiffProps) {
  const [showUnchanged, setShowUnchanged] = useState(false);

  const existing = Array.isArray(data?.existing) ? data.existing : [];
  const proposed = Array.isArray(data?.proposed) ? data.proposed : [];
  const { diffEntries, unchangedEntries } = computePeopleDiff(existing, proposed, recordsDiffer);

  return html`
    <div class="people-diff">
      <div class="people-diff__legend">
        <span class="people-diff__legend-old">Old</span>
        <span class="people-diff__legend-new">New</span>
        ${unchangedEntries.length
          ? html`<button class="people-diff__toggle btn-sm" @click=${() => setShowUnchanged(!showUnchanged)}>
              ${showUnchanged ? "Hide" : `Show ${unchangedEntries.length}`} unchanged
            </button>`
          : ""}
      </div>
      <div class="people-diff__rows">
        ${diffEntries.map(({ type, person, from }) => renderRow(type, from, person))}
        ${showUnchanged ? unchangedEntries.map(({ person, from }) => renderRow("unchanged", from, person)) : ""}
      </div>
    </div>
  `;
}

customElements.define("people-diff", component(PeopleDiff, { useShadowDOM: false }));
