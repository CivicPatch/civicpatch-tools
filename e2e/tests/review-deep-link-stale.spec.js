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
    // 99999999 is well outside the seeded PR-number range (0, 2, 3, 10).
    await page.goto("/review?pull_request_number=99999999");

    // The page must transition out of LOADING to the idle landing within the
    // default Playwright timeout. If the bug is present, the "Loading..." text
    // stays on screen and the start button never renders.
    await expect(page.locator(".review-page__start-btn")).toBeVisible();
  });
});
