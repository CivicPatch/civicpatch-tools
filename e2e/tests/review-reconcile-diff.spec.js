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

    // Maria pairs as a single CHANGED row — guards the existing<->new id pairing.
    const mariaRow = page.locator(".people-diff__person--changed").filter({ hasText: "Maria González" });
    await expect(mariaRow).toBeVisible();

    // Office changed → editable input carries the new value with changed styling.
    const officeInput = mariaRow.locator(".people-diff__field").filter({ hasText: "Office" }).first().locator("input");
    await expect(officeInput).toHaveValue("Council Member");
    await expect(officeInput).toHaveClass(/people-diff__input--changed/);

    // Added email → an added-styled input with the new value (scoped to Maria).
    await expect(mariaRow.locator("input.people-diff__input--added")).toHaveValue("mayor@nh.gov");

    // Removed phone → struck on the old side.
    await expect(
      mariaRow.locator(".people-diff__value--removed").filter({ hasText: "(555) 010-0101" })
    ).toBeVisible();

    // Added-only and removed-only person rows.
    await expect(
      page.locator(".people-diff__person--added").filter({ hasText: "Tom Treasurer" })
    ).toBeVisible();
    await expect(
      page.locator(".people-diff__person--removed").filter({ hasText: "Bob Clerk" })
    ).toBeVisible();

    // Editing round-trips: setting Office back to "Mayor" recomputes the diff live
    // and clears the changed styling.
    await officeInput.fill("Mayor");
    await expect(officeInput).not.toHaveClass(/people-diff__input--changed/);

    // Validation surfaces live: a malformed date flags an inline error.
    const termStartField = mariaRow.locator(".people-diff__field").filter({ hasText: "Term start" }).first();
    const termStartInput = termStartField.locator("input");
    await termStartInput.fill("20-24");
    await expect(termStartInput).toHaveClass(/people-diff__input--error/);
    await expect(termStartField.locator(".people-diff__field-error")).toContainText("YYYY");
  });
});
