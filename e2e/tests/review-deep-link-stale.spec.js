/**
 * User story: a stale or invalid `?card=` in the URL must not leave the review page stuck
 * on the "Loading..." spinner.
 *
 * Repro of the bug being fixed: open /review/session with `?card=X` where X is a request
 * that no longer exists (published, dismissed, or never existed) → the page enters
 * PAGE_STATE.LOADING, the fetch 404s and returns null, and nothing transitions the state
 * machine back out → "Loading..." forever.
 */

import { test, expect } from "../fixtures/index.js";

test.describe("Review deep-link — stale card", () => {
  test("stale ?card= in URL does not freeze the page on Loading", async ({ authenticatedPage: page }) => {
    // A well-formed uuid that matches no seeded request.
    await page.goto("/review/session?card=00000000-0000-0000-ffff-999999999999");

    // Boot fetches the card, gets a 404, and falls back to the /review landing where the
    // start button renders.
    await expect(page.locator(".review-page__start-btn")).toBeVisible();
  });
});
