import { describe, it, expect } from 'vitest';
import { shouldRenderVerifyCta } from '../components/verify-cta/verify-cta-visibility.js';

// This suite used to also gate on isLoggedIn (hidden entirely for anonymous
// visitors). It now renders for anyone with backlog, logged in or not, because
// the CTA itself branches its action (Verify vs Sign in) on auth state instead
// of being hidden — that replaced the duplicate "needs review" messaging that
// used to live in the logged-out contribution card.
describe('shouldRenderVerifyCta', () => {
  it('renders when there is review backlog', () => {
    expect(shouldRenderVerifyCta({ toReviewCount: 5 })).toBe(true);
  });

  it('does not render when backlog is zero', () => {
    expect(shouldRenderVerifyCta({ toReviewCount: 0 })).toBe(false);
  });
});
