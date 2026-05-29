import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchDisplayNameSuggestion, setDisplayName } from "../../api.js";
import "./settings-page.css";

type User = {
  authenticated: boolean;
  display_name: string | null;
};

function SettingsPage({ user }: { user: string }) {
  let userData: User = { authenticated: false, display_name: null };
  try {
    userData = user ? JSON.parse(user) : userData;
  } catch (_e) {
    /* fall through with default */
  }
  const needsDisplayName = !userData.display_name;

  const [value, setValue] = useState(userData.display_name || "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!needsDisplayName) return;
    fetchDisplayNameSuggestion()
      .then((suggestion) => setValue(suggestion))
      .catch(() => {
        /* leave input empty; user can type */
      });
  }, []);

  const onSubmit = async (e: Event) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await setDisplayName(value.trim());
      window.location.href = "/";
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e.message || "Failed to save");
      setSaving(false);
    }
  };

  return html`
    <main class="settings-page page-content">
      ${needsDisplayName
        ? html`<div class="settings-page__banner" role="alert">
            Pick a display name to continue.
          </div>`
        : ""}
      <h1 class="settings-page__title">Settings</h1>
      <form class="settings-page__form" @submit=${onSubmit}>
        <label class="settings-page__label" for="display-name">Display name</label>
        <input
          class="settings-page__input"
          id="display-name"
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
