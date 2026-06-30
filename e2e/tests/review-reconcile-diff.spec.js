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

  test("links an added person to a removed record", async ({ authenticatedPage: page }) => {
    await page.goto(`/review/session?request_id=${RECONCILE_REQUEST_ID}`);
    await expect(page.locator("people-diff")).toBeVisible();

    // Tom is an unmatched ADDED card; Bob is an unmatched REMOVED card.
    const tomAdded = page.locator(".people-diff__person--added").filter({ hasText: "Tom Treasurer" });
    await expect(tomAdded).toBeVisible();
    await expect(page.locator(".people-diff__person--removed").filter({ hasText: "Bob Clerk" })).toBeVisible();

    // Link Tom → Bob via the picker on Tom's card (value is Bob's fixture id).
    await tomAdded.locator(".people-diff__link").selectOption("recon-bob");

    // The removed Bob card is gone; Tom now pairs as a single CHANGED row.
    await expect(page.locator(".people-diff__person--removed").filter({ hasText: "Bob Clerk" })).toHaveCount(0);
    const linked = page.locator(".people-diff__person--changed").filter({ hasText: "Tom Treasurer" });
    await expect(linked).toBeVisible();
    await expect(linked.locator(".people-diff__name")).toHaveText("Tom Treasurer");

    // Old name struck on the old side; folded into other_names so the next scrape matches.
    await expect(linked.locator(".people-diff__cell--old del").filter({ hasText: "Bob Clerk" })).toBeVisible();
    const otherNames = linked.locator(".people-diff__field").filter({ hasText: "Other names" }).first();
    await expect(otherNames.locator("input.people-diff__input--added")).toHaveValue("Bob Clerk");
  });
});
