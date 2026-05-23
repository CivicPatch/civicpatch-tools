import { component, useState } from "haunted";
import { html } from "lit-html";
import type { TemplateResult } from "lit-html";
import { config } from "../../assets/config.js";
import "./email-login.css";

type Step = "enter-email" | "enter-code";

async function postJson(path: string, body: unknown): Promise<Response> {
  return fetch(`${config.apiUrl}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function errorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") return data.detail;
  } catch {
    /* response wasn't JSON; fall through */
  }
  return fallback;
}

function EmailLogin(): TemplateResult {
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
      const response = await postJson("/api/v1/auth/supabase/request-otp", { email });
      if (!response.ok) {
        setErrorMessage(
          await errorDetail(response, `Could not send code (${response.status})`)
        );
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
      const response = await postJson("/api/v1/auth/supabase/verify-otp", { email, code });
      if (!response.ok) {
        setErrorMessage(
          await errorDetail(response, `Verification failed (${response.status})`)
        );
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
            <p class="email-login__hint">
              We sent a 6-digit code to <strong>${email}</strong>.
            </p>
            <label for="email-login-code">Code</label>
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
