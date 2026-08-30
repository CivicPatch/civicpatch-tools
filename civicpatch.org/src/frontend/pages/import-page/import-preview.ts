import { html } from "lit-html";
import { component } from "haunted";
import { type ImportPreview, type RowError } from "./import-types.js";

// What the import found, once it has run. The ocdids themselves are not listed: unreadable in
// bulk, and every rejected one is already named against its own row below.

type ImportPreviewHost = HTMLElement & {
  preview: ImportPreview | null;
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

function ImportPreviewPanel(host: ImportPreviewHost) {
  const preview = host.preview;
  if (!preview) return html``;

  return html`
    <table class="import-summary">
      <tbody>
        <tr>
          <th>rows found</th>
          <td>${preview.rows}</td>
        </tr>
        <tr>
          <th>jurisdictions found</th>
          <td>${preview.jurisdictions_ready.length}</td>
        </tr>
        ${preview.jurisdictions_blocked.length
          ? html`<tr>
              <th>blocked</th>
              <td>${preview.jurisdictions_blocked.length}</td>
            </tr>`
          : null}
      </tbody>
    </table>

    ${preview.errors.length
      ? html`
          <section class="import-section">
            <h3 class="import-section__title">
              Rejected rows <span>[${preview.errors.length}]</span>
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
