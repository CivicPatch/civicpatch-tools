import { html } from "lit-html";
import { component, useState } from "haunted";
import { setUsername } from "../../api.js";
import { usernameError } from "../../components/username-utils.js";
import { SectionNav, overviewSection } from "../../components/section-nav/index.js";
import "../../components/panel/panel.css";
import "./settings-page.css";

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

  const [value, setValue] = useState(userData.username || "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const onSubmit = async (e: Event) => {
    e.preventDefault();
    const validationError = usernameError(value);
    if (validationError) {
      setError(validationError);
      return;
    }
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

      <div class="sectioned">
        ${SectionNav("overview", overviewSection(), "/settings")}
        <div class="secbody">
          <section class="panel">
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
                pattern="[A-Za-z0-9._-]+"
                title="Letters, numbers, '.', '_', and '-' only"
                required
              />
              ${error
                ? html`<div class="settings-page__error" role="alert">${error}</div>`
                : ""}
              <button
                class="settings-page__submit"
                type="submit"
                ?disabled=${saving || !!usernameError(value)}
              >
                ${saving ? "Saving…" : "Save"}
              </button>
            </form>
          </section>
        </div>
      </div>
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
