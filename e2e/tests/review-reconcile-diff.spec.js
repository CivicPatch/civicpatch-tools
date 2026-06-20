/**
 * User story: reviewing a re-scrape (reconcile) renders a real per-field diff.
 *
 * Given a previously-scraped jurisdiction with existing people
 * And a proposed set that changes one, adds one, and drops one
 * When I open its review card
 * Then people-diff shows the changed / added / removed states visually:
 *   - a changed field (office) marked changed
 *   - an added multi value (new email) marked added
 *   - a removed multi value (old phone) struck
 *   - an added-only person row and a removed-only person row
 */

import { test, expect } from "../fixtures/index.js";
import { RECONCILE_REQUEST_ID } from "../fixtures/db.js";

test.describe("Review reconcile diff (populated)", () => {
  test("renders changed / added / removed states", async ({ authenticatedPage: page }) => {
    await page.goto(`/review/session?request_id=${RECONCILE_REQUEST_ID}`);

    // Reconcile mode renders the diff, not the baseline banner.
    await expect(page.locator("people-diff")).toBeVisible();
    await expect(page.locator(".review-page__baseline-banner")).toHaveCount(0);

    // Maria must pair as a single CHANGED row (not added+removed) — guards the
    // existing<->proposed id pairing before the field-level checks.
    await expect(
      page.locator(".people-diff__person--changed").filter({ hasText: "Maria González" })
    ).toBeVisible();

    // Changed scalar field: office Mayor → Council Member.
    await expect(
      page.locator(".people-diff__cell--changed").filter({ hasText: "Council Member" })
    ).toBeVisible();

    // Added multi value: the new email.
    await expect(
      page.locator(".people-diff__value--added").filter({ hasText: "mayor@nh.gov" })
    ).toBeVisible();

    // Removed multi value: the dropped phone, struck on the old side.
    await expect(
      page.locator(".people-diff__value--removed").filter({ hasText: "(555) 010-0101" })
    ).toBeVisible();

    // Added-only and removed-only person rows.
    await expect(
      page.locator(".people-diff__person--added").filter({ hasText: "Tom Treasurer" })
    ).toBeVisible();
    await expect(
      page.locator(".people-diff__person--removed").filter({ hasText: "Bob Clerk" })
    ).toBeVisible();
  });
});
