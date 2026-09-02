/**
 * Regression for the "impossible state" bug: switching the navbar state while a
 * review session is open must never leave a card from the previous state on
 * screen, and must never enable navigation against the wrong state.
 *
 * The fix is structural — /review (landing) and /review/session (the session)
 * are separate routes, and switching state is a full page navigation back to the
 * new state's landing. There is no in-page state to go stale.
 *
 * Repro: NJ (3 PRs) → advance a couple cards → switch to TX (1 PR) → start TX →
 * switch back to NJ → Resume. The visible card always matches the URL's state.
 */

import { test, expect } from "../fixtures/index.js";

test.describe("Review session — rapid state switch", () => {
  test("switching state from within a session never shows the previous state's card", async ({ authenticatedPage: page }) => {
    // Start NJ and advance so the session sits at a non-trivial position.
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page).toHaveURL(/\/review\/session/);
    // One of the seeded NJ jurisdictions — which one is first depends on issue weighting, and
    // this test is about state switching, not queue order.
    await expect(page.locator(".review-page__jurisdiction")).toContainText(/E2E Test City/);
    await page.locator(".review-page__next-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("2");

    // Switch to TX via the navbar — a full nav back to the TX landing. No NJ card.
    await page.locator(".nav-state-selector select").selectOption("tx");
    await expect(page).toHaveURL(/\/review(\?|$)/);
    await expect(
      page.locator(".review-page__jurisdiction").filter({ hasText: /E2E Test City/ }),
    ).toHaveCount(0);

    // Start the lone TX session — TX content only, never NJ.
    await page.locator(".review-page__start-btn").click();
    await expect(page).toHaveURL(/\/review\/session/);
    await expect(page.locator(".review-page__jurisdiction")).toContainText("E2E TX City");
    await expect(
      page.locator(".review-page__jurisdiction").filter({ hasText: /E2E Test City/ }),
    ).toHaveCount(0);

    // Switch back to NJ — the TX card is gone and the NJ landing offers Resume.
    await page.locator(".nav-state-selector select").selectOption("nj");
    await expect(page).toHaveURL(/\/review(\?|$)/);
    await expect(
      page.locator(".review-page__jurisdiction").filter({ hasText: "E2E TX City" }),
    ).toHaveCount(0);
    await expect(page.locator(".review-page__start-btn")).toHaveText(/Resume/);

    // Resume NJ — back at card 2 with NJ content, never TX.
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("2");
    // One of the seeded NJ jurisdictions — which one is first depends on issue weighting, and
    // this test is about state switching, not queue order.
    await expect(page.locator(".review-page__jurisdiction")).toContainText(/E2E Test City/);
    await expect(
      page.locator(".review-page__jurisdiction").filter({ hasText: "E2E TX City" }),
    ).toHaveCount(0);
  });
});
