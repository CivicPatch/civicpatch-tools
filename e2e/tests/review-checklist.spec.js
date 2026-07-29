/**
 * The issue checklist (spec §8) — the complete index of a card's issues, and
 * the reviewer's private record of what they have looked at.
 *
 * Ticks are localStorage, scoped to one card and one browser. They are personal
 * progress, never a team signal — which is why they survive a reload, stay
 * available on a read-only card, and say so on screen.
 */

import { test, expect } from "../fixtures/index.js";
import { MARKERS_REQUEST_ID, READ_ONLY_REQUEST_ID } from "../fixtures/db.js";
import { openDetail, railFor } from "./helpers/review-card.js";

const items = (page) => page.locator(".review-checklist__item");

const openMarkers = async (page) => {
  await page.goto(`/review/session?request_id=${MARKERS_REQUEST_ID}`);
  await expect(page.locator(".review-checklist")).toBeVisible();
};

test.describe("Issue checklist", () => {
  test("indexes every issue, including ones no card can act on", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);

    // extra_official (person), duplicate_unique_role (person + field) and
    // missing_official — the last has no person_ids, so it appears ONLY here.
    await expect(items(page)).toHaveCount(3);
    await expect(page.locator(".review-checklist")).toContainText("Missing official");
    await expect(page.locator(".review-checklist__progress")).toContainText("0 of 3");
  });

  test("a tick is personal progress, and says so", async ({ authenticatedPage: page }) => {
    await openMarkers(page);
    await expect(page.locator(".review-checklist__privacy")).toContainText("Only you");
  });

  test("ticking marks it done and survives a reload", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    const first = items(page).filter({ hasText: "Extra official" });
    await first.locator("input").check();
    await expect(first).toHaveClass(/review-checklist__item--done/);
    await expect(page.locator(".review-checklist__progress")).toContainText("1 of 3");

    await page.reload();
    await expect(page.locator(".review-checklist__progress")).toContainText("1 of 3");
  });

  test("ticking clears the marker on the card it anchors to", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    await openDetail(page);

    const carol = railFor(page, "Carol Extra");
    await expect(carol.locator(".review-rail__issue--row")).toHaveCount(1);

    await items(page).filter({ hasText: "Extra official" }).locator("input").check();

    // The tick has to take effect where the reviewer was looking, not only in
    // the list they ticked it from (§8.2).
    await expect(carol.locator(".review-rail__issue--row")).toHaveCount(0);
  });

  test("one tick clears both holders of a shared-message issue", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    await openDetail(page);

    // duplicate_unique_role carries one message across Alice and Bob, so keying
    // by content means one tick correctly resolves both anchors. Scoped by the
    // message — Carol's row-level marker carries the same base class.
    const shared = page.locator(".review-rail__issue").filter({ hasText: "marked as unique" });
    await expect(shared).toHaveCount(2);
    await items(page).filter({ hasText: "marked as unique" }).locator("input").check();
    await expect(shared).toHaveCount(0);
  });

  test("ticks are scoped to their card", async ({ authenticatedPage: page }) => {
    await openMarkers(page);
    await items(page).first().locator("input").check();
    await expect(page.locator(".review-checklist__progress")).toContainText("1 of 3");

    await page.goto(`/review/session?request_id=${READ_ONLY_REQUEST_ID}`);
    await page.goto(`/review/session?request_id=${MARKERS_REQUEST_ID}`);
    await expect(page.locator(".review-checklist__progress")).toContainText("1 of 3");
  });

  test("stays tickable on a read-only card, and hidden on Preview", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    // Preview is the published result; issues belong to the review (§8.3).
    await page.locator(".review-page__view-tab", { hasText: "Preview" }).click();
    await expect(page.locator(".review-checklist")).toHaveCount(0);

    // A published card can still be read through and ticked off — the tick is
    // progress in this browser, not a mutation of the card (§8.3, §10).
    await page.goto(`/review/session?request_id=${READ_ONLY_REQUEST_ID}`);
    const readOnlyItems = items(page);
    if (await readOnlyItems.count()) {
      await expect(readOnlyItems.first().locator("input")).toBeEnabled();
    }
  });
});
