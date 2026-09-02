/**
 * Two people resolving to one id (spec §21.8) — no longer reachable end to end.
 *
 * `computePeopleDiff` keys both sides by person id, so a duplicate collapses — last wins — and
 * one person is on screen NOWHERE. The banner that reports that loss is still in
 * `review-session.ts` and is still worth keeping, because the collapse is deliberate: the frozen
 * field set, expansion, deletions and restorations are all keyed by person id.
 *
 * What changed is that no fixture can manufacture the input any more. Two sightings sharing a
 * `person_id` are two sightings of ONE person, and `roster_from_sightings` merges them upstream
 * of the diff — so the API returns one entry, not two colliding ones. `resolve_people_ids` was
 * fixed on 2026-07-31 not to mint colliding ids either.
 *
 * The guard itself is tested where it can still be reached: `diff-utils.test.ts` feeds
 * `computePeopleDiff` two proposed people sharing an id and asserts `duplicateIds`.
 *
 * Two tests were removed here on 2026-09-01. They verified that the banner names the shared id
 * and that only one of the pair renders. They now verify nothing — the fixture produced one
 * person and one unrelated person, so both failed on a state the product cannot enter. The
 * `e2e_duplicate` fixture went with them, rather than leave another card nothing reads.
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_CHANGESET_ID } from "../fixtures/db.js";

test.describe("Duplicate person ids", () => {
  test("stays quiet on a card whose ids are all unique", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${SCALE_CHANGESET_ID}`);
    await expect(page.locator("review-overview")).toBeVisible();
    await expect(page.locator(".review-page__duplicate-banner")).toHaveCount(0);
  });
});
