/**
 * Two people resolving to one id (spec §21.8).
 *
 * `computePeopleDiff` keys both sides by person id, so a duplicate collapses —
 * last wins — and one person is on screen NOWHERE: not added, not changed, not
 * removed. Publishing then sends a single record and the other entry's data is
 * lost without ever having been shown.
 *
 * The collapse is kept, because the frozen field set, expansion, deletions and
 * restorations are all keyed by person id and would be ambiguous otherwise. What
 * these assert is that the loss is now *reported* rather than silent.
 */

import { test, expect } from "../fixtures/index.js";
import { DUPLICATE_REQUEST_ID, SCALE_REQUEST_ID } from "../fixtures/db.js";
import { openDetail } from "./helpers/review-card.js";

test.describe("Duplicate person ids", () => {
  test("says so, and names the id", async ({ authenticatedPage: page }) => {
    await page.goto(`/review/session?changeset_id=${DUPLICATE_REQUEST_ID}`);

    const banner = page.locator(".review-page__duplicate-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText("share an id");
    await expect(banner).toContainText("dup-shared");
  });

  test("only one of the pair is rendered — which is the harm being reported", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${DUPLICATE_REQUEST_ID}`);
    await openDetail(page);

    // Three proposed people, two sharing an id, so two editors.
    await expect(page.locator(".person-editor:not(.person-editor--ghost)")).toHaveCount(2);
    await expect(page.locator(".person-editor__name").filter({ hasText: "Sam Single" })).toBeVisible();

    // Last wins, so the first of the pair is the one that vanished.
    await expect(
      page.locator(".person-editor__name").filter({ hasText: "Pat Duplicate the Second" }),
    ).toBeVisible();
  });

  test("stays quiet on a card whose ids are all unique", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${SCALE_REQUEST_ID}`);
    await expect(page.locator("review-overview")).toBeVisible();
    await expect(page.locator(".review-page__duplicate-banner")).toHaveCount(0);
  });
});
