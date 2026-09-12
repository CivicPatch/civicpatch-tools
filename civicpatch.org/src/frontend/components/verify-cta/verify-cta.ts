import "./verify-cta.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { shouldRenderVerifyCta } from "./verify-cta-visibility.js";
import {
  landingUrl,
  sessionUrl,
  DEFAULT_SESSION_LENGTH,
} from "../../pages/review-routes.js";
import { SESSION_COUNTS } from "../../pages/review-page/review-landing.js";
import { createReviewSession, navigateToEntry } from "../../api.js";

interface VerifyCtaProps {
  isLoggedIn?: boolean;
  toReviewCount?: number;
  state?: string;
  hasActiveSession?: boolean;
}

function VerifyCta({
  isLoggedIn = false,
  toReviewCount = 0,
  state = "",
  hasActiveSession = false,
}: VerifyCtaProps) {
  // Not persisted — the backend already remembers the length from this user's last
  // session (create_or_get_review_session falls back to it when none is passed), so
  // caching a second copy here would just be a weaker, device-scoped duplicate of
  // that. This is only what the reader has explicitly picked in this page view.
  const [sessionLength, setSessionLength] = useState<number | undefined>(undefined);
  const [starting, setStarting] = useState(false);

  if (!shouldRenderVerifyCta({ toReviewCount })) return html``;

  // A resumable session can jump straight to it. Otherwise, start one the same
  // way the /review landing page's own button does (createReviewSession, then
  // claim its first entry) — a plain link to /review/session can't do this,
  // since boot() there only resumes an *existing* session.
  const handleVerifyClick = async () => {
    if (hasActiveSession) {
      window.location.href = sessionUrl(state);
      return;
    }
    setStarting(true);
    try {
      const session = (await createReviewSession(state, sessionLength)).data;
      await navigateToEntry(session.id, session.next_entry_number);
      window.location.href = sessionUrl(state);
    } catch {
      window.location.href = landingUrl(state);
    }
  };

  // No picker at all once a session is already resumable — length was decided when
  // that session started, so offering to change it here would change nothing.
  const lengthPicker = isLoggedIn && !hasActiveSession
    ? html`
        <span class="verify-cta__lengths">
          ${SESSION_COUNTS.map(
            (n) => html`
              <button
                type="button"
                class="verify-cta__length ${n === sessionLength ? "verify-cta__length--active" : ""}"
                ?disabled=${n > toReviewCount}
                @click=${() => setSessionLength(n)}
              >
                ${n}
              </button>
            `,
          )}
        </span>
      `
    : "";

  return isLoggedIn
    ? html`
        ${lengthPicker}
        <button
          class="verify-cta"
          type="button"
          ?disabled=${starting}
          @click=${handleVerifyClick}
        >
          review ${hasActiveSession ? toReviewCount : (sessionLength ?? DEFAULT_SESSION_LENGTH)}${state ? html` in #${state}` : ""}
        </button>
      `
    : html`
        <a class="verify-cta" href="/login">
          sign in to review ${toReviewCount}${state ? html` in #${state}` : ""}
        </a>
      `;
}

customElements.define(
  "civ-verify-cta",
  component(VerifyCta as any, { useShadowDOM: false, observedAttributes: [] }),
);
