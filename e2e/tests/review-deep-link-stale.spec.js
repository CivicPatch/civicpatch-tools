/**
 * User story: a stale or invalid `?pull_request_number=` in the URL must not
 * leave the review page stuck on the "Loading..." spinner.
 *
 * Repro of the bug being fixed: refresh /review with `?pull_request_number=N`
 * where N is a PR that no longer exists (closed/merged, or never existed) →
 * the page enters PAGE_STATE.LOADING, loadDirectPr returns null on the 404,
 * and nothing transitions the state machine back out → "Loading..." forever.
 */

import { test, expect } from "../fixtures/index.js";

test.describe("Review deep-link — stale pull_request_number", () => {
  test("stale ?pull_request_number= in URL does not freeze the page on Loading", async ({ authenticatedPage: page }) => {
    // Deeplinks now live on /review/session. 99999999 is well outside the seeded
    // PR-number range (0, 2, 3, 10).
    await page.goto("/review/session?pull_request_number=99999999");

    // A stale PR must not freeze on "Loading..." — boot fetches the PR, gets a
    // 404, and falls back to the /review landing where the start button renders.
    await expect(page.locator(".review-page__start-btn")).toBeVisible();
  });
});
