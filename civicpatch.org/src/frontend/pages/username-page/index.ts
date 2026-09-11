import { html } from "lit-html";
import type { TemplateResult } from "lit-html";
import { component, useState } from "haunted";
import { setUsername } from "../../api.js";
import "../../components/panel/panel.css";
import "./username-page.css";

function UsernamePage(): TemplateResult {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

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
    <section class="panel username-page">
      <div class="panel__cap"><b>one more step</b></div>
      <p class="username-page__hint">Pick a username before you continue.</p>
      <form class="username-page__form" @submit=${onSubmit}>
        <label for="username-page-input">Username</label>
        <input
          id="username-page-input"
          type="text"
          autocomplete="username"
          maxlength="50"
          required
          autofocus
          .value=${value}
          @input=${(e: Event) => setValue((e.target as HTMLInputElement).value)}
        />
        ${error
          ? html`<p role="alert" class="username-page__error">${error}</p>`
          : ""}
        <button type="submit" ?disabled=${saving || !value.trim()}>
          ${saving ? "Saving…" : "Continue"}
        </button>
      </form>
    </section>
  `;
}

customElements.define(
  "username-page",
  component(UsernamePage, { useShadowDOM: false }),
);
