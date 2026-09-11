import { html } from "lit-html";
import { component, useState } from "haunted";
import { setUsername } from "../../api.js";
import "./api-keys.js";
import { canManageApiKeys } from "./api-key-access.js";
import "../../components/civ-tab-bar/civ-tab-bar.js";
import "../../components/panel/panel.css";
import "./settings-page.css";

const PROFILE_TAB = 0;
const API_KEYS_TAB = 1;
const TABS = [{ label: "Profile" }, { label: "API keys" }];

type User = {
  authenticated: boolean;
  username: string | null;
  permissions?: { can_write_config?: boolean };
};

function SettingsPage({ user }: { user: string }) {
  let userData: User = { authenticated: false, username: null };
  try {
    userData = user ? JSON.parse(user) : userData;
  } catch (_e) {
    /* fall through with default */
  }
  const canHoldKeys = canManageApiKeys(userData);

  const [value, setValue] = useState(userData.username || "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState(PROFILE_TAB);

  const onSubmit = async (e: Event) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await setUsername(value.trim());
      window.location.href = "/";
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e.message || "Failed to save");
      setSaving(false);
    }
  };

  return html`
    <main class="settings-page page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Settings</h1>
      </div>

      ${canHoldKeys
        ? html`<civ-tab-bar
            .tabs=${TABS}
            .selectedIndex=${tab}
            .onTabClick=${(index: number) => setTab(index)}
          ></civ-tab-bar>`
        : null}

      ${tab === PROFILE_TAB || !canHoldKeys
        ? html`<section class="panel">
            <div class="panel__cap"><b>username</b></div>
            <form class="settings-page__form" @submit=${onSubmit}>
              <label class="settings-page__label" for="username">Username</label>
              <input
                class="settings-page__input"
                id="username"
                type="text"
                .value=${value}
                @input=${(e: Event) => setValue((e.target as HTMLInputElement).value)}
                maxlength="50"
                required
              />
              ${error
                ? html`<div class="settings-page__error" role="alert">${error}</div>`
                : ""}
              <button
                class="settings-page__submit"
                type="submit"
                ?disabled=${saving || !value.trim()}
              >
                ${saving ? "Saving…" : "Save"}
              </button>
            </form>
          </section>`
        : null}

      ${canHoldKeys && tab === API_KEYS_TAB
        ? html`<api-keys></api-keys>`
        : null}
    </main>
  `;
}

customElements.define(
  "settings-page",
  component(SettingsPage as never, {
    useShadowDOM: false,
    observedAttributes: ["user"],
  }),
);
