import { html } from "lit-html";
import { component } from "haunted";
import { type ImportPreview } from "./import-types.js";
import {
  jurisdictionOcdidToFriendly,
  jurisdictionOcdidToPath,
} from "../../components/ocdid-utils.js";

// What the import found, once it has run. Rejected rows are listed on their batch, where they
// outlive a refresh.

type ImportPreviewHost = HTMLElement & {
  preview: ImportPreview | null;
};

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
  `;
}

customElements.define(
  "import-preview",
  component(ImportPreviewPanel as unknown as () => unknown, {
    useShadowDOM: false,
  }),
);
