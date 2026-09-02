/**
 * User story: structured reviewer issues surface as per-card markers on the diff.
 *
 * Given a proposed set whose review_json carries structured issues
 * When I open its review card
 * Then the editor anchors each person-scoped issue to its card:
 *   - new_person (no field) → a row-level marker above the card's fields
 *   - duplicate_unique_role (field post_id) → a marker under the Post field
 *     of each named holder
 *   - absent_person (no person_ids) → stays list-level, never a card marker
 * And editing a marked card clears its marker (clear-on-edit).
 *
 * An anchored issue also keeps its field visible even when nothing about that
 * field moved — rule 2 of the collapse rule (§2), and the reason these two
 * holders show a Post row at all.
 *
 * The messages are asserted verbatim because they are the ones `build_review_summary`
 * produces. An earlier version of this spec quoted a `markersReview` object in the fixture
 * that nothing has read since the summary stopped being frozen at ingest, so its wording
 * ("Extra official", "Dropped official") never reached a page.
 */

import { test, expect } from "../fixtures/index.js";
import { MARKERS_CHANGESET_ID } from "../fixtures/db.js";
import { openDetail, editorFor, editField } from "./helpers/review-card.js";

test.describe("Review issue markers", () => {
  test("anchors person-scoped issues to their cards; list-level stays off the diff", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${MARKERS_CHANGESET_ID}`);
    await openDetail(page);

    // Row-level: new_person (no field) → marker on Carol's card, above the fields.
    await expect(
      editorFor(page, "Carol Extra")
        .locator(".person-editor__issue--row")
        .filter({ hasText: "New person found: Carol Extra" }),
    ).toBeVisible();

    // Field-level: duplicate_unique_role (field post_id) → a marker under the Post
    // row of each named holder, and that row is only on screen because the issue
    // anchors to it.
    for (const name of ["Alice Mayor", "Bob Council"]) {
      const seat = editorFor(page, name)
        .locator(".person-editor__field")
        .filter({ hasText: "Post" });
      await expect(seat).toHaveCount(1);
      await expect(seat.locator(".person-editor__issue")).toContainText(
        "marked as unique",
      );
    }

    // List-level: absent_person has no person_ids → it never becomes a card marker.
    await expect(
      page
        .locator(".person-editor__issue")
        .filter({ hasText: "Not found in this scrape" }),
    ).toHaveCount(0);
  });

  test("clear-on-edit: editing a marked card drops its marker", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${MARKERS_CHANGESET_ID}`);
    await openDetail(page);

    const carol = editorFor(page, "Carol Extra");
    await expect(carol.locator(".person-editor__issue")).toHaveCount(1);

    // Any edit that leaves her name alone, so the locator stays valid → card goes dirty → its
    // marker is presumed addressed and clears. Other names rather than the seat: the seat is a
    // select now, and this is about dirtiness, not about what was edited. Through `editField`
    // because her issue anchors to no field, so nothing of hers is on screen until expanded.
    await editField(page, "Carol Extra", "Other names", "Caroline Extra");
    await expect(carol.locator(".person-editor__issue")).toHaveCount(0);
  });
});
