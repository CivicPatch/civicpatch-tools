import { html } from "lit-html";
import { component } from "haunted";
import { type ImportPreview, type RowError } from "./import-types.js";

const START_EVENT = "start-import";

type ImportPreviewHost = HTMLElement & {
  preview: ImportPreview | null;
  busy: boolean;
};

function errorRow(error: RowError) {
  return html`
    <tr>
      <td class="import-errors__line">${error.line}</td>
      <td class="import-cell--ocdid">${error.jurisdiction_ocdid}</td>
      <td>${error.column ?? "-"}</td>
      <td>${error.message}</td>
    </tr>
  `;
}

function blockedList(ocdids: string[]) {
  if (!ocdids.length) return null;
  return html`
    <section class="import-section">
      <h3 class="import-section__title">Blocked <span>${ocdids.length}</span></h3>
      <p class="import-hint">
        A row in these localities was rejected. A locality imports whole or not
        at all, so fix the rows below and check again.
      </p>
      <ul class="import-list">
        ${ocdids.map(
          (ocdid) => html`<li class="import-cell--ocdid">${ocdid}</li>`,
        )}
      </ul>
    </section>
  `;
}

function ImportPreviewPanel(host: ImportPreviewHost) {
  const preview = host.preview;

  if (!preview) {
    return html`
      <p class="import-empty">
        Check the sheet to see what an import would do. Nothing is written until
        you start one.
      </p>
    `;
  }

  const ready = preview.jurisdictions_ready;

  // Importing is not the destructive step: it stops at ingest and raises review cards, so
  // there is nothing to choose here. Publishing is where the picking happens.
  const handleStart = () =>
    host.dispatchEvent(
      new CustomEvent(START_EVENT, { bubbles: true, composed: true }),
    );

  return html`
    <section class="import-section">
      <h3 class="import-section__title">
        Ready <span>[${ready.length}]</span>
      </h3>
      <p class="import-hint">
        ${preview.rows} row${preview.rows === 1 ? "" : "s"} read. Each locality
        becomes a review card. Nothing is published until you say so.
      </p>

      ${ready.length
        ? html`<ul class="import-list import-list--scrolls">
            ${ready.map(
              (ocdid) => html`<li class="import-cell--ocdid">${ocdid}</li>`,
            )}
          </ul>`
        : html`<p class="import-hint">Nothing ready to import.</p>`}

      <button
        type="button"
        class="import-action"
        ?disabled=${host.busy || !ready.length}
        @click=${handleStart}
      >
        Import
      </button>
    </section>

    ${blockedList(preview.jurisdictions_blocked)}

    ${preview.errors.length
      ? html`
          <section class="import-section">
            <h3 class="import-section__title">
              Rejected rows <span>${preview.errors.length}</span>
            </h3>
            <table class="import-errors__table">
              <thead>
                <tr>
                  <th>Line</th>
                  <th>Locality</th>
                  <th>Column</th>
                  <th>Problem</th>
                </tr>
              </thead>
              <tbody>
                ${preview.errors.map(errorRow)}
              </tbody>
            </table>
          </section>
        `
      : null}
  `;
}

customElements.define(
  "import-preview",
  component(ImportPreviewPanel as unknown as () => unknown, {
    useShadowDOM: false,
  }),
);
