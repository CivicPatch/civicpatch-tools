/**
 * User story: when the session has no further PRs to claim, the Next button
 * must be visibly disabled so the user can't fall through to a silent
 * "session ended" with no explanation.
 *
 * Repro target: TX fixture seeds exactly 1 open PR. After clicking Start,
 * the card loads and `has_next` is false — the Next button must reflect that.
 */

import { test, expect } from "../fixtures/index.js";

test.describe("Review session — Next button disabled", () => {
  test("Next button is disabled when only one PR is available in the session", async ({ authenticatedPage: page }) => {
    // Switch to TX (seed has exactly 1 open PR there). "/" is a global route
    // (no state selector) — switch from a state-scoped page instead.
    await page.goto("/review");
    await page.locator(".nav-state-selector select").selectOption("tx");

    // Start the session and confirm the lone TX card loaded
    await page.locator(".review-page__start-btn").click();
    await expect(page.getByText("E2E TX City")).toBeVisible();

    // With only one PR in the pool, `has_next` from the navigate response is
    // false and the Next button must be rendered with the disabled attribute.
    await expect(page.locator(".review-page__next-btn")).toBeDisabled();
  });
});
