import { component, useState } from "haunted";
import { html } from "lit-html";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import "./diff-panel.css";

const FIELDS = [
  { key: "name",                  label: "Name" },
  { key: "office.name",           label: "Office" },
  { key: "office.division_ocdid", label: "Division" },
  { key: "phones",                label: "Phones" },
  { key: "emails",                label: "Emails" },
  { key: "urls",                  label: "URLs" },
  { key: "start_date",            label: "Start Date" },
  { key: "end_date",              label: "End Date" },
  { key: "image",                 label: "Image" }
];

function getFieldValue(person, key) {
  let val;
  if (key === "office.name")            val = person?.office?.name;
  else if (key === "office.division_ocdid") val = person?.office?.division_ocdid;
  else                                   val = person?.[key];
  if (Array.isArray(val)) return val.join(", ");
  return val ?? "";
}

function displayValue(key, raw) {
  if (key === "office.division_ocdid") return divisionOcdidToFriendly(raw) || raw || "—";
  return raw || "—";
}

function normalizeForCompare(val) {
  return val.toLowerCase().trim();
}

function changedFields(existing, pr) {
  return FIELDS.filter(
    ({ key }) => normalizeForCompare(getFieldValue(existing, key)) !== normalizeForCompare(getFieldValue(pr, key)),
  );
}

const DiffPanel = ({ data }) => {
  const [showUnchanged, setShowUnchanged] = useState(false);

  const existingData = Array.isArray(data?.existing) ? data.existing : [];
  const prData = Array.isArray(data?.pull_request) ? data.pull_request : [];
  const existingMap = Object.fromEntries(existingData.map((p) => [p?.id, p]));
  const prMap = Object.fromEntries(prData.map((p) => [p?.id, p]));
  const allKeys = Array.from(new Set([...Object.keys(existingMap), ...Object.keys(prMap)]));

  const diffEntries = [];
  const unchangedEntries = [];

  for (const key of allKeys) {
    const existing = existingMap[key];
    const pr = prMap[key];
    if (!existing)
      diffEntries.push({ type: "added", person: pr, from: null });
    else if (!pr)
      diffEntries.push({ type: "removed", person: existing, from: existing });
    else if (changedFields(existing, pr).length > 0)
      diffEntries.push({ type: "changed", person: pr, from: existing });
    else
      unchangedEntries.push({ type: "unchanged", person: pr, from: existing });
  }

  function renderAdded(person) {
    return html`
      <div class="diff-person diff-person--added">
        <div class="diff-person__header">
          <span class="diff-person__badge diff-person__badge--added">+</span>
          <span class="diff-person__name">${person.name || "—"}</span>
        </div>
        <table class="diff-person__fields">
          ${FIELDS.filter(({ key }) => key !== "name").map(({ key, label }) => {
            const val = getFieldValue(person, key);
            if (!val) return "";
            return html`<tr>
              <td class="diff-field__label">${label}</td>
              <td><ins>${displayValue(key, val)}</ins></td>
            </tr>`;
          })}
        </table>
      </div>
    `;
  }

  function renderRemoved(person) {
    return html`
      <div class="diff-person diff-person--removed">
        <div class="diff-person__header">
          <span class="diff-person__badge diff-person__badge--removed">−</span>
          <span class="diff-person__name">${person.name || "—"}</span>
        </div>
        <table class="diff-person__fields">
          ${FIELDS.filter(({ key }) => key !== "name").map(({ key, label }) => {
            const val = getFieldValue(person, key);
            if (!val) return "";
            return html`<tr>
              <td class="diff-field__label">${label}</td>
              <td><del>${displayValue(key, val)}</del></td>
            </tr>`;
          })}
        </table>
      </div>
    `;
  }

  function renderChanged(person, from) {
    const fields = changedFields(from, person);
    return html`
      <div class="diff-person diff-person--changed">
        <div class="diff-person__header">
          <span class="diff-person__badge diff-person__badge--changed">~</span>
          <span class="diff-person__name">${person.name || from?.name || "—"}</span>
        </div>
        <table class="diff-person__fields">
          ${fields.map(({ key, label }) => html`<tr>
            <td class="diff-field__label">${label}</td>
            <td class="diff-field__before"><del>${displayValue(key, getFieldValue(from, key))}</del></td>
            <td class="diff-field__after"><ins>${displayValue(key, getFieldValue(person, key))}</ins></td>
          </tr>`)}
        </table>
      </div>
    `;
  }

  function renderUnchanged(person) {
    return html`
      <div class="diff-person diff-person--unchanged">
        <div class="diff-person__header">
          <span class="diff-person__badge">·</span>
          <span class="diff-person__name">${person.name || "—"}</span>
        </div>
      </div>
    `;
  }

  if (diffEntries.length === 0 && unchangedEntries.length === 0) {
    return html`<div class="diff-panel"><p class="diff-panel__empty">No data.</p></div>`;
  }

  return html`
    <div class="diff-panel">
      <div class="diff-panel__toolbar">
        <span class="diff-panel__label">Changes Since Last Scrape</span>
        ${diffEntries.length === 0
          ? html`<span class="diff-panel__summary">No changes detected.</span>`
          : ""}
        ${unchangedEntries.length > 0 ? html`
          <button
            class="diff-panel__toggle btn-sm"
            @click=${() => setShowUnchanged(!showUnchanged)}
          >${showUnchanged ? "Hide" : `Show ${unchangedEntries.length}`} unchanged</button>
        ` : ""}
      </div>
      <div class="diff-panel__entries">
        ${diffEntries.map(({ type, person, from }) =>
          type === "added"   ? renderAdded(person) :
          type === "removed" ? renderRemoved(person) :
                               renderChanged(person, from)
        )}
        ${showUnchanged ? unchangedEntries.map(({ person }) => renderUnchanged(person)) : ""}
      </div>
    </div>
  `;
};

customElements.define(
  "civ-diff-panel",
  component(DiffPanel, { useShadowDOM: false }),
);
