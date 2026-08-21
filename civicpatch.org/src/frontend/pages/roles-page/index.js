import { html } from "lit-html";
import { component } from "haunted";
import "../issues-page/config-editor.js";
import "../../components/unmatched-text/unmatched-text.ts";

function RolesPage() {
  return html`
    <main class="page-content">
      <issues-config-editor .inline=${true}></issues-config-editor>
      <section>
        <h2>Unmatched</h2>
        <unmatched-text></unmatched-text>
      </section>
    </main>
  `;
}

customElements.define("roles-page", component(RolesPage, { useShadowDOM: false }));
