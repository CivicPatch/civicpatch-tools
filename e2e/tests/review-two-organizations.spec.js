/**
 * A review card whose changeset read two organizations.
 *
 * The projector plan assumed this could not happen — "a review card is one body by
 * construction — a review is scoped to a changeset — which is why it never needed any of
 * this" (§14, 9b(c)) — and that sentence is why the review page was left keying its open
 * editor by person id while the roster page moved to `cardKey`.
 *
 * It is false: a source record names its own `organization_id`, so one changeset's records
 * span as many bodies as it read pages for, which is what `_one_post_each`'s own docstring
 * assumes. `TWO_ORG_CHANGESET_ID` is such a scrape — Ada listed under the council and the
 * school board — and until 2026-09-24 the card mishandled it three ways at once: she rendered
 * three times, nothing said which body a row was about, and clicking one row opened the
 * editor in all three.
 *
 * Both pages now emit one row per (person, body) from `buildPersonCards` and key on
 * `cardKey`, which is what this holds down.
 */

import { test, expect } from "../fixtures/index.js";
import { TWO_ORG_CHANGESET_ID, TWO_BODY_COUNCIL, TWO_BODY_SCHOOL_BOARD } from "../fixtures/db.js";

test("a card that read two bodies keeps them apart", async ({
  authenticatedPage: page,
}) => {
  await page.goto(`/review/session?changeset_id=${TWO_ORG_CHANGESET_ID}`);
  await expect(page.locator("review-overview")).toBeVisible();

  // One row per body she is in, not one per membership on either side.
  const ada = page.locator("review-overview .rperson").filter({ hasText: "Ada Two-Body" });
  await expect(ada).toHaveCount(2);

  // And each section says which body it is, the way the jurisdiction page heads its own.
  const organizations = page.locator("review-overview .review-overview__organization .panel__cap b");
  await expect(organizations).toContainText([TWO_BODY_COUNCIL, TWO_BODY_SCHOOL_BOARD]);

  // Opening one row opens one editor — the thing `cardKey` exists for.
  await ada.first().locator(".pc-name").click();
  await expect(page.locator(".person-editor-inline")).toHaveCount(1);
});
