import "./diff-panel.css";
import "../person-image.js";
import { component, useState } from "haunted";
import { html, nothing } from "lit-html";
import { computePeopleDiff, DiffType } from "../../utils/diff-utils.js";
import { SOURCE_LINK_TARGET } from "../../utils/source-links.js";
import { FIELDS, getFieldValue, displayValue, changedFields } from "./diff-fields.ts";

const POST_FIELD_KEY = "labels";

const BADGE_LABEL = {
  [DiffType.ADDED]: "new",
  [DiffType.REMOVED]: "removed",
  [DiffType.CHANGED]: "changed",
};

const DiffPanel = ({ data }) => {
  const [showUnchanged, setShowUnchanged] = useState(false);

  const existingData = Array.isArray(data?.existing) ? data.existing : [];
  const prData = Array.isArray(data?.proposed) ? data.proposed : [];
  const { diffEntries, unchangedEntries } = computePeopleDiff(
    existingData,
    prData,
    (e, p) => changedFields(e, p).length > 0,
  );

  function renderSourceLinks(person) {
    const urls = person?.source_urls;
    if (!urls?.length) return nothing;
    return html`<span class="diff-person__src">${urls.map((url, i) =>
      html`<a class="source-link" href=${url} target=${SOURCE_LINK_TARGET}>[${i + 1}]</a>`,
    )}</span>`;
  }

  // Name and avatar identify who; the badge and source links are metadata, pushed to the
  // trailing edge with a margin-left: auto on the badge (see diff-panel.css).
  function renderHeader(person, type) {
    return html`
      <div class="diff-person__header">
        <person-image
          .person=${{ name: person?.name, cdn_image: person?.cdn_image }}
          .size=${"1.75rem"}
        ></person-image>
        <span class="diff-person__name">${person?.name || "—"}</span>
        ${type
          ? html`<span class="diff-person__badge diff-person__badge--${type}">${BADGE_LABEL[type]}</span>`
          : nothing}
        ${renderSourceLinks(person)}
      </div>
    `;
  }

  function renderFieldValue(type, key, from, person) {
    const oldRaw = getFieldValue(from, key);
    const newRaw = getFieldValue(person, key);
    const oldVal = displayValue(key, oldRaw);
    const newVal = displayValue(key, newRaw);
    if (type === DiffType.ADDED) return html`<ins>${newVal}</ins>`;
    if (type === DiffType.REMOVED) return html`<del>${oldVal}</del>`;
    // A field going from genuinely empty to populated (or the reverse) is one-sided —
    // showing a struck-through "—" placeholder next to it reads as noise, not a real diff.
    if (!oldRaw) return html`<ins>${newVal}</ins>`;
    if (!newRaw) return html`<del>${oldVal}</del>`;
    return html`<del>${oldVal}</del> <ins>${newVal}</ins>`;
  }

  // Post is the substance of a diff review — full weight. Phones/emails/urls are
  // present but not competing for attention, so they stay small and muted.
  function renderFieldRow(key, label, type, from, person) {
    return html`<span class="diff-person__field ${key === POST_FIELD_KEY ? "diff-person__field--post" : ""}">
      <span class="diff-field__label">${label}</span>
      <span class="diff-field__value">${renderFieldValue(type, key, from, person)}</span>
    </span>`;
  }

  function renderPersonCard(type, person, from) {
    const record = type === DiffType.REMOVED ? from : person;
    const fields =
      type === DiffType.CHANGED
        ? changedFields(from, person)
        : FIELDS.filter(({ key }) => key !== "name" && getFieldValue(record, key));
    return html`
      <div class="diff-person diff-person--${type}">
        ${renderHeader(record, type)}
        <div class="diff-person__fields">
          ${fields.map(({ key, label }) => renderFieldRow(key, label, type, from, person))}
        </div>
      </div>
    `;
  }

  function renderUnchanged(person) {
    return html`<div class="diff-person diff-person--unchanged">${renderHeader(person, null)}</div>`;
  }

  if (diffEntries.length === 0 && unchangedEntries.length === 0) {
    return html``;
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
        ${diffEntries.map(({ type, person, from }) => renderPersonCard(type, person, from))}
        ${showUnchanged ? unchangedEntries.map(({ person }) => renderUnchanged(person)) : ""}
      </div>
    </div>
  `;
};

customElements.define(
  "civ-diff-panel",
  component(DiffPanel, { useShadowDOM: false }),
);
