/**
 * User story: structured reviewer issues surface as per-card markers on the diff.
 *
 * Given a proposed set whose review_json carries structured issues
 * When I open its review card
 * Then people-diff anchors each person-scoped issue to its card:
 *   - extra_official (no field) → a row-level marker above the card's fields
 *   - duplicate_unique_role (field office.name) → a marker under the Office field
 *     of each named holder
 *   - missing_official (no person_ids) → stays list-level, never a card marker
 * And editing a marked card clears its marker (clear-on-edit).
 */

import { test, expect } from "../fixtures/index.js";
import { MARKERS_REQUEST_ID } from "../fixtures/db.js";

test.describe("Review issue markers", () => {
  test("anchors person-scoped issues to their cards; list-level stays off the diff", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?request_id=${MARKERS_REQUEST_ID}`);
    await expect(page.locator("people-diff")).toBeVisible();

    // Scope by the name span, which holds only the card's own name — the
    // duplicate-role message names both holders, so a card-wide hasText would
    // match more than one card.
    const cardByName = (name) =>
      page.locator(".people-diff__person").filter({ has: page.locator(".people-diff__name", { hasText: name }) });

    // Row-level: extra_official (no field) → marker on Carol's card, above the fields.
    await expect(
      cardByName("Carol Extra").locator(".people-diff__issue").filter({ hasText: "Extra official: Carol Extra" })
    ).toBeVisible();

    // Field-level: duplicate_unique_role (field office.name) → a marker inside the
    // fields grid on each named holder (Alice and Bob).
    await expect(
      cardByName("Alice Mayor").locator(".people-diff__fields .people-diff__issue").filter({ hasText: "marked as unique" })
    ).toBeVisible();
    await expect(
      cardByName("Bob Council").locator(".people-diff__fields .people-diff__issue").filter({ hasText: "marked as unique" })
    ).toBeVisible();

    // List-level: missing_official has no person_ids → it never becomes a card marker.
    await expect(
      page.locator(".people-diff__issue").filter({ hasText: "Missing official" })
    ).toHaveCount(0);
  });

  test("clear-on-edit: editing a marked card drops its marker", async ({ authenticatedPage: page }) => {
    await page.goto(`/review/session?request_id=${MARKERS_REQUEST_ID}`);

    const carol = page.locator(".people-diff__person").filter({ hasText: "Carol Extra" });
    await expect(carol.locator(".people-diff__issue")).toHaveCount(1);

    // Edit Carol's Office (leaves her name, so the locator stays valid) → card goes
    // dirty → its marker is presumed addressed and clears.
    const officeInput = carol
      .locator(".people-diff__field")
      .filter({ hasText: "Office" })
      .first()
      .locator("input");
    await officeInput.fill("Trustee");
    await expect(carol.locator(".people-diff__issue")).toHaveCount(0);
  });
});
