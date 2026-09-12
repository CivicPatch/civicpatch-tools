import { html } from "lit-html";
import { component } from "haunted";
import "../settings-page/api-keys.js";
import { canManageApiKeys } from "../settings-page/api-key-access.js";
import { SectionNav, overviewSection } from "../../components/section-nav/index.js";
import "../../components/panel/panel.css";
import "../settings-page/settings-page.css";

type User = {
  authenticated: boolean;
  username: string | null;
  permissions?: { can_write_config?: boolean };
};

function SettingsApiKeysPage({ user }: { user: string }) {
  let userData: User = { authenticated: false, username: null };
  try {
    userData = user ? JSON.parse(user) : userData;
  } catch (_e) {
    /* fall through with default */
  }
  const canHoldKeys = canManageApiKeys(userData);

  return html`
    <main class="settings-page page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Settings</h1>
      </div>

      <div class="sectioned">
        ${SectionNav("overview", overviewSection(), "/settings/api-keys")}
        <div class="secbody">${canHoldKeys ? html`<api-keys></api-keys>` : null}</div>
      </div>
    </main>
  `;
}

customElements.define(
  "settings-api-keys-page",
  component(SettingsApiKeysPage as never, {
    useShadowDOM: false,
    observedAttributes: ["user"],
  }),
);
