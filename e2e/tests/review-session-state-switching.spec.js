/**
 * User story: switching navbar state isolates review sessions per state.
 *
 * Repro of the bug being fixed: pick state A → start a review → leave the
 * page → pick state B in the navbar → return to /review → the page must
 * show the idle landing for B, NOT resume state A's session.
 */

import { test, expect } from "../fixtures/index.js";

test.describe("Review session — state switching", () => {
  test("switching navbar state shows the new state's content, not the previous state's session", async ({ authenticatedPage: page }) => {
    // Start a review session in NJ (seeded by the fixture)
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.getByText(/E2E Test City/)).toBeVisible();

    // Leave the review page
    await page.goto("/");

    // Switch to TX via the navbar selector
    await page.locator(".nav-state-selector select").selectOption("tx");

    // Return to /review — must show TX idle landing, NOT the resumed NJ session
    await page.goto("/review");
    await expect(page.locator(".review-page__start-btn")).toBeVisible();
    await expect(page.getByText(/E2E Test City/)).not.toBeVisible();
    await expect(page.locator(".review-page__end-btn")).not.toBeVisible();

    // Start a fresh TX session — positive assertion that we land on the TX
    // jurisdiction (not bleeding NJ content into a TX-scoped session)
    await page.locator(".review-page__start-btn").click();
    await expect(page.getByText("E2E TX City")).toBeVisible();
    await expect(page.getByText(/E2E Test City/)).not.toBeVisible();
  });

  test("switching back to the original state resumes its session and stays in that state when navigating onward", async ({ authenticatedPage: page }) => {
    // Start NJ session and advance to card 2 so resume position is non-trivial
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.getByText(/E2E Test City/)).toBeVisible();
    await page.locator(".review-page__next-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("2");

    // Leave, switch to TX, return — NJ session must be hidden (idle landing for TX)
    await page.goto("/");
    await page.locator(".nav-state-selector select").selectOption("tx");
    await page.goto("/review");
    await expect(page.locator(".review-page__start-btn")).toBeVisible();

    // Switch back to NJ. This previously asserted /review itself resumed the
    // session; it now asserts the NJ landing offers Resume (session still active)
    // and resuming restores card 2, because resume is an explicit step post-split.
    await page.locator(".nav-state-selector select").selectOption("nj");
    await expect(page.locator(".review-page__start-btn")).toHaveText(/Resume/);
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("2");
    // Card is one of the seeded NJ jurisdictions (all start with "E2E Test City")
    await expect(page.getByText(/E2E Test City/)).toBeVisible();

    // Click next from the resumed position — the following card is also NJ,
    // proving the session has not silently leaked into the TX namespace.
    await page.locator(".review-page__next-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("3");
    await expect(page.getByText(/E2E Test City/)).toBeVisible();
  });
});
