import { html } from "lit-html";
import { component } from "haunted";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import "../issues-page/config-editor.js";

function RolesPage() {
  const [stateCode] = useLocalStorage("app:default-state", "", { ttl: PERSIST_FOREVER });

  return html`
    <main class="page-content">
      <issues-config-editor .inline=${true} .stateCode=${stateCode}></issues-config-editor>
    </main>
  `;
}

customElements.define("roles-page", component(RolesPage, { useShadowDOM: false }));
