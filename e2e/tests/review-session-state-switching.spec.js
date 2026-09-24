/**
 * User story: review sessions are isolated per state.
 *
 * Repro of the bug being fixed: start a review in state A → look at state B → the page must
 * show the idle landing for B, NOT resume state A's session.
 *
 * State used to travel in a navbar picker every page followed. It travels in the URL now
 * (`review-routes.ts`'s `landingUrl`, `?state=`), and the picker that remains on
 * `/bulk-review` scopes that page alone — so switching there cannot move `/review`, and these
 * navigate directly. The claim is unchanged: one state's session must not surface in another.
 */

import { test, expect } from "../fixtures/index.js";

test.describe("Review session — state switching", () => {
  test("switching navbar state shows the new state's content, not the previous state's session", async ({ authenticatedPage: page }) => {
    // Start a review session in NJ (seeded by the fixture)
    await page.goto("/review?state=nj");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-session__jurisdiction")).toContainText(/E2E Test City/);

    // Look at TX — must show the TX idle landing, NOT the resumed NJ session
    await page.goto("/review?state=tx");
    await expect(page.locator(".review-page__start-btn")).toBeVisible();
    await expect(
      page.locator(".review-session__jurisdiction").filter({ hasText: /E2E Test City/ }),
    ).toHaveCount(0);
    await expect(page.locator(".review-session__end-btn")).not.toBeVisible();

    // Start a fresh TX session — positive assertion that we land on the TX
    // jurisdiction (not bleeding NJ content into a TX-scoped session)
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-session__jurisdiction")).toContainText("E2E TX City");
    await expect(
      page.locator(".review-session__jurisdiction").filter({ hasText: /E2E Test City/ }),
    ).toHaveCount(0);
  });

  test("switching back to the original state resumes its session and stays in that state when navigating onward", async ({ authenticatedPage: page }) => {
    // Start NJ session and advance to card 2 so resume position is non-trivial
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-session__jurisdiction")).toContainText(/E2E Test City/);
    await page.locator(".review-session__next-btn").click();
    await expect(page.locator(".review-session__progress")).toContainText("2");

    // Look at TX — the NJ session must be hidden (idle landing for TX)
    await page.goto("/review?state=tx");
    await expect(page.locator(".review-page__start-btn")).toBeVisible();

    // Switch back to NJ. This previously asserted /review itself resumed the
    // session; it now asserts the NJ landing offers Resume (session still active)
    // and resuming restores card 2, because resume is an explicit step post-split.
    await page.goto("/review?state=nj");
    await expect(page.locator(".review-page__start-btn")).toHaveText(/Resume/);
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-session__progress")).toContainText("2");
    // Card is one of the seeded NJ jurisdictions (all start with "E2E Test City")
    await expect(page.locator(".review-session__jurisdiction")).toContainText(/E2E Test City/);

    // Click next from the resumed position — the following card is also NJ,
    // proving the session has not silently leaked into the TX namespace.
    await page.locator(".review-session__next-btn").click();
    await expect(page.locator(".review-session__progress")).toContainText("3");
    await expect(page.locator(".review-session__jurisdiction")).toContainText(/E2E Test City/);
  });
});
