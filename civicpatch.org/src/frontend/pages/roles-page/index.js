import { html } from "lit-html";
import { component } from "haunted";
import "../issues-page/config-editor.js";
import "../../components/unmatched-text/unmatched-text.ts";
import { useAuth } from "../../hooks/useAuth.js";
import { SectionNav, manageSection } from "../../components/section-nav/index.js";
import { useSummary } from "../../hooks/useSummary.js";

function RolesPage() {
  const { permissions } = useAuth();
  // Global, not scoped to any page's own state — the sidebar badge is a constant
  // "how much is waiting overall" figure, the same wherever it appears.
  const globalSummary = useSummary(true, "");
  return html`
    <main class="page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Roles</h1>
      </div>
      <div class="sectioned">
        ${SectionNav("manage", manageSection(permissions, globalSummary?.open_prs), "/roles")}
        <div class="secbody">
          <issues-config-editor .inline=${true}></issues-config-editor>
          <section>
            <h2>Unmatched</h2>
            <unmatched-text></unmatched-text>
          </section>
        </div>
      </div>
    </main>
  `;
}

customElements.define("roles-page", component(RolesPage, { useShadowDOM: false }));
