import { html } from "lit-html";
import { component } from "haunted";
import { type ImportPreview, type RowError } from "./import-types.js";
import {
  jurisdictionOcdidToFriendly,
  jurisdictionOcdidToPath,
} from "../../components/ocdid-utils.js";

// What the import found, once it has run. Localities read as their town name and link to the
// jurisdiction, so a rejected row is one click from the page that explains it — the raw ocdid
// is unreadable in bulk and tells you nothing you can act on.

type ImportPreviewHost = HTMLElement & {
  preview: ImportPreview | null;
};

/** A town name linking to its jurisdiction, or nothing when the row named no jurisdiction —
 * which is what a row missing its `jurisdiction_ocdid` looks like. */
function locality(jurisdiction_ocdid: string) {
  const path = jurisdictionOcdidToPath(jurisdiction_ocdid);
  if (!path) return html`<td></td>`;
  return html`
    <td>
      <a href="/${path}" title=${jurisdiction_ocdid}
        >${jurisdictionOcdidToFriendly(jurisdiction_ocdid)}</a
      >
    </td>
  `;
}

function errorRow(error: RowError) {
  return html`
    <tr>
      <td class="import-errors__line">${error.line}</td>
      ${locality(error.jurisdiction_ocdid)}
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
          <td>
            ${preview.jurisdictions_ready.length}
            ${preview.jurisdictions_ready.length
              ? html`&mdash;
                  ${preview.jurisdictions_ready.map(
                    (ocdid, index) => html`${index ? ", " : ""}
                      <a href="/${jurisdictionOcdidToPath(ocdid)}" title=${ocdid}
                        >${jurisdictionOcdidToFriendly(ocdid)}</a
                      >`,
                  )}`
              : null}
          </td>
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
