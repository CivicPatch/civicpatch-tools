import { component, useMemo, useState } from "haunted";
import { html } from "lit-html";
import type { TemplateResult } from "lit-html";
import { createClient } from "@supabase/supabase-js";
import { config } from "../../assets/config.js";

type Step = "enter-email" | "enter-code";

function SupabaseLogin(host: HTMLElement): TemplateResult {
  const client = useMemo(() => {
    const url = host.dataset.supabaseUrl;
    const publishableKey = host.dataset.publishableKey;
    if (!url || !publishableKey) {
      throw new Error("civ-supabase-login: missing required data attributes");
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

  return html`
    ${errorMessage
      ? html`<p role="alert" class="supabase-login__error">${errorMessage}</p>`
      : ""}
    ${step === "enter-email"
      ? html`
          <form @submit=${sendCode}>
            <label for="supabase-email">Email</label>
            <input
              id="supabase-email"
              type="email"
              autocomplete="email"
              required
              .value=${email}
              @input=${(e: InputEvent) =>
                setEmail((e.target as HTMLInputElement).value)}
            />
            <button type="submit" ?disabled=${busy}>Send code</button>
          </form>
        `
      : html`
          <p>
            We sent a 6-digit code to <strong>${email}</strong>. Enter it below.
          </p>
          <form @submit=${verifyCode}>
            <label for="supabase-code">Code</label>
            <input
              id="supabase-code"
              inputmode="numeric"
              autocomplete="one-time-code"
              pattern="[0-9]*"
              required
              .value=${code}
              @input=${(e: InputEvent) =>
                setCode((e.target as HTMLInputElement).value)}
            />
            <button type="submit" ?disabled=${busy}>Verify</button>
          </form>
        `}
  `;
}

customElements.define(
  "civ-supabase-login",
  component(SupabaseLogin, { useShadowDOM: false })
);
