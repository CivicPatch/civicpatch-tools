import { html } from "lit-html";
import { component } from "haunted";
import "../issues-page/config-editor.js";

function RolesPage() {
  return html`
    <main class="page-content">
      <issues-config-editor .inline=${true}></issues-config-editor>
    </main>
  `;
}

customElements.define("roles-page", component(RolesPage, { useShadowDOM: false }));
