/**
 * User story: structured reviewer issues surface as per-card markers on the diff.
 *
 * Given a proposed set whose review_json carries structured issues
 * When I open its review card
 * Then the editor anchors each person-scoped issue to its card:
 *   - extra_official (no field) → a row-level marker above the card's fields
 *   - duplicate_unique_role (field office.name) → a marker under the Office field
 *     of each named holder
 *   - missing_official (no person_ids) → stays list-level, never a card marker
 * And editing a marked card clears its marker (clear-on-edit).
 *
 * An anchored issue also keeps its field visible even when nothing about that
 * field moved — rule 2 of the collapse rule (§2), and the reason these two
 * holders show an Office row at all.
 */

import { test, expect } from "../fixtures/index.js";
import { MARKERS_REQUEST_ID } from "../fixtures/db.js";
import { openDetail, editorFor } from "./helpers/review-card.js";

test.describe("Review issue markers", () => {
  test("anchors person-scoped issues to their cards; list-level stays off the diff", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?request_id=${MARKERS_REQUEST_ID}`);
    await openDetail(page);

    // Row-level: extra_official (no field) → marker on Carol's card, above the fields.
    await expect(
      editorFor(page, "Carol Extra")
        .locator(".person-editor__issue--row")
        .filter({ hasText: "Extra official: Carol Extra" }),
    ).toBeVisible();

    // Field-level: duplicate_unique_role (field office.name) → a marker under the
    // Office row of each named holder, and that row is only on screen because the
    // issue anchors to it.
    for (const name of ["Alice Mayor", "Bob Council"]) {
      const office = editorFor(page, name)
        .locator(".person-editor__field")
        .filter({ hasText: "Office" });
      await expect(office).toHaveCount(1);
      await expect(office.locator(".person-editor__issue")).toContainText(
        "marked as unique",
      );
    }

    // List-level: missing_official has no person_ids → it never becomes a card marker.
    await expect(
      page
        .locator(".person-editor__issue")
        .filter({ hasText: "Dropped official" }),
    ).toHaveCount(0);
  });

  test("clear-on-edit: editing a marked card drops its marker", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?request_id=${MARKERS_REQUEST_ID}`);
    await openDetail(page);

    const carol = editorFor(page, "Carol Extra");
    await expect(carol.locator(".person-editor__issue")).toHaveCount(1);

    // Edit Carol's Office (leaves her name, so the locator stays valid) → card goes
    // dirty → its marker is presumed addressed and clears.
    await carol
      .locator(".person-editor__field")
      .filter({ hasText: "Office" })
      .first()
      .locator("input")
      .fill("Trustee");
    await expect(carol.locator(".person-editor__issue")).toHaveCount(0);
  });
});
