import './verify-cta.css';
import { html } from 'lit-html';
import { component } from 'haunted';
import { shouldRenderVerifyCta } from './verify-cta-visibility.js';

interface VerifyCtaProps {
  isLoggedIn?: boolean;
  toReviewCount?: number;
}

function VerifyCta({ isLoggedIn = false, toReviewCount = 0 }: VerifyCtaProps) {
  if (!shouldRenderVerifyCta({ isLoggedIn, toReviewCount })) return html``;

  return html`
    <div class="verify-cta">
      <p class="verify-cta__count">${toReviewCount}</p>
      <p class="verify-cta__description">
        ${toReviewCount === 1 ? 'municipality needs' : 'municipalities need'} review before publishing.
      </p>
      <a class="verify-cta__link" href="/review">Verify officials →</a>
    </div>
  `;
}

customElements.define(
  'civ-verify-cta',
  component(VerifyCta as any, { useShadowDOM: false, observedAttributes: [] }),
);
