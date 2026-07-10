import "./verify-cta.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { shouldRenderVerifyCta } from "./verify-cta-visibility.js";
import {
  landingUrl,
  sessionUrl,
  DAILY_GOAL_KEY,
  DEFAULT_DAILY_GOAL,
} from "../../pages/review-routes.js";
import {
  useLocalStorage,
  PERSIST_FOREVER,
} from "../../hooks/use-local-storage.js";
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
  const [dailyGoal] = useLocalStorage(DAILY_GOAL_KEY, DEFAULT_DAILY_GOAL, {
    ttl: PERSIST_FOREVER,
  });
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
      const session = (await createReviewSession(state, dailyGoal)).data;
      await navigateToEntry(session.id, session.next_entry_number);
      window.location.href = sessionUrl(state);
    } catch {
      window.location.href = landingUrl(state);
    }
  };

  return html`
    <div class="verify-cta">
      <p class="verify-cta__count">${toReviewCount}</p>
      <p class="verify-cta__description">
        ${toReviewCount === 1 ? "municipality needs" : "municipalities need"} a
        review before publishing.
      </p>
      ${isLoggedIn
        ? html`<button
            class="verify-cta__link"
            type="button"
            ?disabled=${starting}
            @click=${handleVerifyClick}
          >
            Verify officials <i class="fa-solid fa-arrow-right"></i>
          </button>`
        : html`<a class="verify-cta__link" href="/login">
            Sign in to review data <i class="fa-solid fa-arrow-right"></i>
          </a>`}
    </div>
  `;
}

customElements.define(
  "civ-verify-cta",
  component(VerifyCta as any, { useShadowDOM: false, observedAttributes: [] }),
);
