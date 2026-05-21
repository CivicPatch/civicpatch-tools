import { component, useMemo, useState } from "haunted";
import { html } from "lit-html";
import type { TemplateResult } from "lit-html";
import { createClient } from "@supabase/supabase-js";
import { config } from "../../assets/config.js";
import "./email-login.css";

type Step = "enter-email" | "enter-code";

function EmailLogin(host: HTMLElement): TemplateResult {
  const client = useMemo(() => {
    const url = host.dataset.supabaseUrl;
    const publishableKey = host.dataset.publishableKey;
    if (!url || !publishableKey) {
      throw new Error("civ-email-login: missing required data attributes");
    }
    return createClient(url, publishableKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    });
  }, []);

  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<Step>("enter-email");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function sendCode(event: Event) {
    event.preventDefault();
    setErrorMessage(null);
    if (!email) return;
    setBusy(true);
    try {
      const { error } = await client.auth.signInWithOtp({
        email,
        options: { shouldCreateUser: true },
      });
      if (error) {
        setErrorMessage(error.message);
        return;
      }
      setStep("enter-code");
    } finally {
      setBusy(false);
    }
  }

  async function verifyCode(event: Event) {
    event.preventDefault();
    setErrorMessage(null);
    if (!code) return;
    setBusy(true);
    try {
      const { data, error } = await client.auth.verifyOtp({
        email,
        token: code,
        type: "email",
      });
      if (error) {
        setErrorMessage(error.message);
        return;
      }
      const accessToken = data.session?.access_token;
      if (!accessToken) {
        setErrorMessage("Verification returned no access token");
        return;
      }
      const response = await fetch(
        `${config.apiUrl}/api/v1/auth/supabase/callback`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ access_token: accessToken }),
        }
      );
      if (!response.ok) {
        setErrorMessage(`Server rejected the sign-in (${response.status})`);
        return;
      }
      window.location.href = "/";
    } finally {
      setBusy(false);
    }
  }

  const codeRequested = step === "enter-code";
  const onSubmit = codeRequested ? verifyCode : sendCode;

  function clearForm() {
    setStep("enter-email");
    setEmail("");
    setCode("");
    setErrorMessage(null);
  }

  return html`
    ${errorMessage
      ? html`<p role="alert" class="email-login__error">${errorMessage}</p>`
      : ""}
    <form @submit=${onSubmit} class="email-login__form">
      <label for="email-login-email">Email</label>
      <input
        id="email-login-email"
        type="email"
        autocomplete="email"
        required
        ?disabled=${codeRequested}
        .value=${email}
        @input=${(e: InputEvent) =>
          setEmail((e.target as HTMLInputElement).value)}
      />
      ${codeRequested
        ? html`
            <button
              type="button"
              class="btn-ghost email-login__reset"
              ?disabled=${busy}
              @click=${clearForm}
            >
              Wrong email?
            </button>
            <label for="email-login-code">6-digit code</label>
            <input
              id="email-login-code"
              inputmode="numeric"
              autocomplete="one-time-code"
              pattern="[0-9]*"
              required
              autofocus
              .value=${code}
              @input=${(e: InputEvent) =>
                setCode((e.target as HTMLInputElement).value)}
            />
          `
        : ""}
      <button type="submit" ?disabled=${busy}>
        ${codeRequested ? "Verify" : "Send code"}
      </button>
    </form>
  `;
}

customElements.define(
  "civ-email-login",
  component(EmailLogin, { useShadowDOM: false })
);
