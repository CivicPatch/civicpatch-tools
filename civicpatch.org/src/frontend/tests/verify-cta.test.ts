import { describe, it, expect } from 'vitest';
import { shouldRenderVerifyCta } from '../components/verify-cta/verify-cta-visibility.js';

describe('shouldRenderVerifyCta', () => {
  it('renders when logged in and there is review backlog', () => {
    expect(shouldRenderVerifyCta({ isLoggedIn: true, toReviewCount: 5 })).toBe(true);
  });

  it('does not render when logged in but backlog is zero', () => {
    expect(shouldRenderVerifyCta({ isLoggedIn: true, toReviewCount: 0 })).toBe(false);
  });

  it('does not render when logged out, even with backlog', () => {
    expect(shouldRenderVerifyCta({ isLoggedIn: false, toReviewCount: 5 })).toBe(false);
  });

  it('does not render when logged out and backlog is zero', () => {
    expect(shouldRenderVerifyCta({ isLoggedIn: false, toReviewCount: 0 })).toBe(false);
  });
});
