import { html } from "lit-html";
import { component } from "haunted";
import {
  type ImportPreview,
  type RowError,
} from "./import-types.js";

const START_EVENT = "start-import";

type ImportPreviewHost = HTMLElement & {
  preview: ImportPreview | null;
  busy: boolean;
};

function errorRow(error: RowError) {
  return html`
    <tr>
      <td class="import-errors__line">${error.line}</td>
      <td>${error.jurisdiction_ocdid}</td>
      <td>${error.column ?? "—"}</td>
      <td>${error.message}</td>
    </tr>
  `;
}

function townList(title: string, hint: string, ocdids: string[]) {
  if (!ocdids.length) return null;
  return html`
    <section class="import-towns">
      <h3 class="import-towns__title">${title} <span>${ocdids.length}</span></h3>
      <p class="import-towns__hint">${hint}</p>
      <ul class="import-towns__list">
        ${ocdids.map((ocdid) => html`<li>${ocdid}</li>`)}
      </ul>
    </section>
  `;
}

function ImportPreviewPanel(host: ImportPreviewHost) {
  const preview = host.preview;

  const handleStart = () =>
    host.dispatchEvent(
      new CustomEvent(START_EVENT, { bubbles: true, composed: true }),
    );

  if (!preview) {
    return html`
      <p class="import-empty">
        Check the sheet to see what an import would do. Nothing is written until
        you start one.
      </p>
    `;
  }

  const ready = preview.jurisdictions_ready;
  return html`
    <p class="import-summary">
      ${preview.rows} row${preview.rows === 1 ? "" : "s"} read.
    </p>

    ${townList(
      "Ready",
      "Marked ready, and every row parsed.",
      ready,
    )}
    ${townList(
      "Blocked",
      "A row in these towns was rejected. A town imports whole or not at all, " +
        "so fix the rows below and check again.",
      preview.jurisdictions_blocked,
    )}
    ${townList(
      "Not marked ready",
      "Rows exist, but nobody has ticked ready on the Jurisdictions tab.",
      preview.jurisdictions_skipped,
    )}

    ${preview.errors.length
      ? html`
          <section class="import-errors">
            <h3 class="import-towns__title">
              Rejected rows <span>${preview.errors.length}</span>
            </h3>
            <table class="import-errors__table">
              <thead>
                <tr>
                  <th>Line</th>
                  <th>Jurisdiction</th>
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

    <button
      type="button"
      class="import-action"
      ?disabled=${host.busy || !ready.length}
      @click=${handleStart}
    >
      ${ready.length
        ? `Import ${ready.length} town${ready.length === 1 ? "" : "s"}`
        : "Nothing to import"}
    </button>
  `;
}

customElements.define(
  "import-preview",
  component(ImportPreviewPanel as unknown as () => unknown, {
    useShadowDOM: false,
  }),
);
