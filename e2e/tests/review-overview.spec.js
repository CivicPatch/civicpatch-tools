/**
 * Overview (spec §4) — triage a whole card at a glance, at ?view=overview.
 *
 * The collapse rule decides what a tile says, and §3's predicate decides which
 * group a person lands in. Both are shared with the rail, so these assert that
 * the two views agree rather than re-testing the model.
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_REQUEST_ID } from "../fixtures/db.js";

const openOverview = async (page, requestId = SCALE_REQUEST_ID) => {
  await page.goto(`/review/session?request_id=${requestId}&view=overview`);
  await expect(page.locator("review-overview")).toBeVisible();
};

const tileFor = (page, name) =>
  page
    .locator(".review-tile")
    .filter({ has: page.locator(".review-tile__name", { hasText: name }) });

test.describe("Review overview", () => {
  test("splits the card into what needs review and the roster that doesn't", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    // 10 changed + 5 added + 3 the scrape dropped = 18; the other 25 are untouched.
    const counts = page.locator(".review-overview__count");
    await expect(counts).toHaveText(["18", "25"]);

    // Unchanged people are faces, not tiles — the roster reads complete without
    // spending a card each.
    await expect(page.locator(".review-overview__faces .review-face")).toHaveCount(25);
    await expect(tileFor(page, "Councillor 03 Scale")).toHaveCount(0);
  });

  test("a tile names the fields that moved, not just that something did", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    const tile = tileFor(page, "Councillor 02 Scale");
    await expect(tile.locator(".review-tile__field")).toHaveText(["Term end", "Phone"]);
    await expect(tile).toHaveClass(/review-tile--changed/);
    await expect(tile.locator(".review-tile__badge")).toHaveText("2");
  });

  test("an issue outranks the field count and colours the badge", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    // Councillor 09 carries duplicate_unique_role, anchored to office.name.
    const tile = tileFor(page, "Councillor 09 Scale");
    await expect(tile.locator(".review-tile__badge")).toHaveClass(/review-tile__badge--issue/);
    await expect(tile.locator(".review-tile__badge")).toHaveText("1");
    await expect(tile.locator(".review-tile__field")).toHaveText(["Office"]);
  });

  test("a departing person is one decision — struck, and no field count", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    const tile = tileFor(page, "Councillor 36 Scale");
    await expect(tile).toHaveClass(/review-tile--removed/);
    // With no new-side record every field reads cleared; a count here would say
    // "9 things to review" about a card that is one decision.
    await expect(tile.locator(".review-tile__badge")).toHaveCount(0);
    await expect(tile.locator(".review-tile__field")).toHaveCount(0);
  });

  test("the add-person ghost ends the To review group", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    // In that group because a new person has surviving fields and lands there —
    // after the face strip it would promise the wrong slot.
    const grid = page.locator(".review-overview__grid");
    await expect(grid.locator(".review-tile--ghost")).toHaveCount(1);
    await expect(grid.locator(".review-tile").last()).toHaveClass(/review-tile--ghost/);
  });

  test("opening a person leads somewhere, and the URL remembers the view", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    // Until the modal lands, a tile switches to Detail rather than doing nothing.
    await tileFor(page, "Councillor 02 Scale").locator(".review-tile__open").click();
    await expect(page.locator("review-rail-list")).toBeVisible();
    await expect(page).toHaveURL(/view=detail/);
  });
});
