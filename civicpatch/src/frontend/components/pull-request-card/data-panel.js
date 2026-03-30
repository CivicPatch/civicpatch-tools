import { component, useState } from "haunted";
import { html } from "lit-html";
import { divisionOcdidToFriendly } from "../ocdid-utils";
import { computePeopleDiff } from "../../utils/diff-utils.js";

const DataPanel = ({ entry }) => {
  const [showUnchanged, setShowUnchanged] = useState(false);

  const existingData = Array.isArray(entry?.existing) ? entry.existing : [];
  const prData = Array.isArray(entry?.proposed) ? entry.proposed : [];
  const { diffEntries: diffRows, unchangedEntries: unchangedRows } = computePeopleDiff(
    existingData,
    prData,
    (e, p) =>
      (e.office?.name || "") !== (p.office?.name || "") ||
      (e.office?.division_ocdid || "") !== (p.office?.division_ocdid || ""),
  );

  // ─── Row renderer ──────────────────────────────────────────────────────────

  function renderRow({ row, type }) {
    const name = row.person.name;
    const beforeRole = row.from?.office?.name || row.person.office?.name || "—";
    const afterRole = row.person.office?.name || "—";
    const beforeDiv =
      divisionOcdidToFriendly(row.from?.office?.division_ocdid) || "—";
    const afterDiv =
      divisionOcdidToFriendly(row.person.office?.division_ocdid) || "—";

    const sourceUrls = Array.from(
      new Set([
        ...(row.person?.source_urls || []),
        ...(row.from?.source_urls || []),
      ]),
    );

    const urlLinks = sourceUrls.map(
      (url, i) =>
        html`<a class="source-link" href=${url} target="_blank" rel="noopener"
          >[${i}]</a
        >`,
    );

    if (type === "added")
      return html` <tr class="row--added">
        <td><ins>${name}</ins></td>
        <td></td>
        <td><ins>${afterRole}</ins></td>
        <td><ins>${afterDiv}</ins></td>
        <td>${urlLinks}</td>
      </tr>`;

    if (type === "removed")
      return html` <tr class="row--removed">
        <td><del>${name}</del></td>
        <td><del>${beforeRole}</del></td>
        <td></td>
        <td><del>${beforeDiv}</del></td>
        <td>${urlLinks}</td>
      </tr>`;

    if (type === "changed") {
      const roleChanged = beforeRole !== afterRole;
      const divChanged = beforeDiv !== afterDiv;
      return html` <tr class="row--changed">
        <td>${name}</td>
        <td class="${roleChanged ? "cell--changed" : ""}">
          <del>${beforeRole}</del>
        </td>
        <td class="${roleChanged ? "cell--changed" : ""}">
          <ins>${afterRole}</ins>
        </td>
        <td class="${divChanged ? "cell--changed" : ""}">
          ${divChanged
            ? html`<del>${beforeDiv}</del> <ins>${afterDiv}</ins>`
            : afterDiv}
        </td>
        <td>${urlLinks}</td>
      </tr>`;
    }

    if (type === "unchanged")
      return html` <tr class="row--unchanged">
        <td>${name}</td>
        <td>${beforeRole}</td>
        <td>${afterRole}</td>
        <td>${afterDiv}</td>
        <td>${urlLinks}</td>
      </tr>`;

    return null;
  }

  if (diffRows.length === 0 && unchangedRows.length === 0) {
    return html`<div class="diff-panel">
      <p class="diff-panel__empty">No data.</p>
    </div>`;
  }

  if (diffRows.length === 0 && !showUnchanged) {
    return html` <div class="diff-panel">
      <div class="diff-panel__toolbar">
        <span class="diff-panel__summary">No changes detected.</span>
        <button
          class="diff-panel__toggle"
          @click=${() => setShowUnchanged(true)}
        >
          Show ${unchangedRows.length} unchanged
        </button>
      </div>
    </div>`;
  }

  return html`
    <div class="diff-panel">
      <div class="diff-panel__toolbar">
        ${unchangedRows.length > 0
          ? html` <button
              class="diff-panel__toggle"
              @click=${() => setShowUnchanged(!showUnchanged)}
            >
              ${showUnchanged ? "Hide" : `Show ${unchangedRows.length}`}
              unchanged
            </button>`
          : ""}
      </div>
      <table class="diff-table">
        <colgroup>
          <col class="col-name" />
          <col class="col-before" />
          <col class="col-after" />
          <col class="col-div" />
          <col class="col-src" />
        </colgroup>
        <thead>
          <tr>
            <th>Name</th>
            <th>Before</th>
            <th>After</th>
            <th>Division</th>
            <th>Src</th>
          </tr>
        </thead>
        <tbody>
          ${diffRows.map((row) => renderRow({ row, type: row.type }))}
          ${showUnchanged
            ? unchangedRows.map((row) => renderRow({ row, type: row.type }))
            : ""}
        </tbody>
      </table>
    </div>
  `;
};

customElements.define(
  "data-panel",
  component(DataPanel, { useShadowDOM: false }),
);
