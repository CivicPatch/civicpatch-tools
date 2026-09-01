/**
 * The issue checklist (spec §8) — the complete index of a card's issues, and
 * the reviewer's private record of what they have looked at.
 *
 * Ticks are localStorage, scoped to one card and one browser. They are personal
 * progress, never a team signal — which is why they survive a reload, stay
 * available on a read-only card, and say so on screen.
 *
 * The checklist lives in a drawer opened from the step-nav, so every test here
 * opens it first. The trigger is the only thing on screen saying unresolved
 * issues exist, which is why its count is asserted alongside the list.
 *
 * The drawer is one scrolling pane: the ticks, then By source beneath them.
 */

import { test, expect } from "../fixtures/index.js";
import { MARKERS_REQUEST_ID, READ_ONLY_REQUEST_ID } from "../fixtures/db.js";
import { openDetail, editorFor } from "./helpers/review-card.js";

const items = (page) => page.locator(".review-sidebar__item");
const trigger = (page) => page.locator(".review-sidebar__trigger");
const count = (page) => page.locator(".review-sidebar__trigger-count");

const openDrawer = async (page) => {
  await trigger(page).click();
  await expect(page.locator(".review-sidebar")).toBeVisible();
};

const closeDrawer = async (page) => {
  await page.keyboard.press("Escape");
  await expect(page.locator(".review-sidebar")).toHaveAttribute("inert", "");
};

const openMarkers = async (page) => {
  await page.goto(`/review/session?changeset_id=${MARKERS_REQUEST_ID}`);
  await expect(trigger(page)).toBeVisible();
};

test.describe("Issue checklist", () => {
  test("indexes every issue, including ones no card can act on", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    await openDrawer(page);

    // new_official (person), duplicate_unique_role (person + field) and
    // absent_official — the last has no person_ids, so it appears ONLY here.
    await expect(items(page)).toHaveCount(3);
    await expect(page.locator(".review-sidebar")).toContainText(
      "Dropped official",
    );
    await expect(count(page)).toContainText("0/3");
  });

  test("a tick is personal progress, and says so", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    await openDrawer(page);
    await expect(page.locator(".review-sidebar__privacy")).toContainText(
      "Only you",
    );
  });

  test("ticking marks it done and survives a reload", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    await openDrawer(page);
    const first = items(page).filter({ hasText: "Extra official" });
    await first.locator("input").check();
    await expect(first).toHaveClass(/review-sidebar__item--done/);
    await expect(count(page)).toContainText("1/3");

    // The count is on the trigger, so a reload proves persistence without
    // reopening the drawer.
    await page.reload();
    await expect(count(page)).toContainText("1/3");
  });

  test("ticking clears the marker on the card it anchors to", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    // Detail first: once the drawer is open its scrim covers the view tabs.
    await openDetail(page);

    const carol = editorFor(page, "Carol Extra");
    await expect(carol.locator(".person-editor__issue--row")).toHaveCount(1);

    await openDrawer(page);
    await items(page)
      .filter({ hasText: "Extra official" })
      .locator("input")
      .check();

    // The tick has to take effect where the reviewer was looking, not only in
    // the list they ticked it from (§8.2).
    await expect(carol.locator(".person-editor__issue--row")).toHaveCount(0);
  });

  test("one tick clears both holders of a shared-message issue", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    await openDetail(page);

    // duplicate_unique_role carries one message across Alice and Bob, so keying
    // by content means one tick correctly resolves both anchors. Scoped by the
    // message — Carol's row-level marker carries the same base class.
    const shared = page
      .locator(".person-editor__issue")
      .filter({ hasText: "marked as unique" });
    await expect(shared).toHaveCount(2);

    await openDrawer(page);
    await items(page)
      .filter({ hasText: "marked as unique" })
      .locator("input")
      .check();
    await expect(shared).toHaveCount(0);
  });

  test("ticks are scoped to their card", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    await openDrawer(page);
    await items(page).first().locator("input").check();
    await expect(count(page)).toContainText("1/3");

    await page.goto(`/review/session?changeset_id=${READ_ONLY_REQUEST_ID}`);
    await page.goto(`/review/session?changeset_id=${MARKERS_REQUEST_ID}`);
    await expect(count(page)).toContainText("1/3");
  });

  test("stays tickable on a read-only card", async ({
    authenticatedPage: page,
  }) => {
    // A published card can still be read through and ticked off — the tick is
    // progress in this browser, not a mutation of the card (§8.3, §10).
    await page.goto(`/review/session?changeset_id=${READ_ONLY_REQUEST_ID}`);
    await openDrawer(page);
    const readOnlyItems = items(page);
    if (await readOnlyItems.count()) {
      await expect(readOnlyItems.first().locator("input")).toBeEnabled();
    }
  });

  // Reverses the previous "hidden on Preview" rule. That test verified the
  // checklist is hidden on Preview (§8.3 — issues belong to the review, not the
  // published roster). It now verifies the trigger stays available there,
  // because the trigger is the only signal that unresolved issues exist and
  // hiding it on the tab where publishing is decided is worse than the reason
  // for hiding it.
  test("stays reachable from the Preview tab", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    await page
      .locator(".review-page__view-tab", { hasText: "Preview" })
      .click();

    await expect(trigger(page)).toBeVisible();
    await expect(count(page)).toContainText("0/3");

    await openDrawer(page);
    await expect(items(page)).toHaveCount(3);
  });

  test("closes on Escape and returns focus to the trigger", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    await openDrawer(page);
    await closeDrawer(page);
    await expect(trigger(page)).toBeFocused();
  });

  test("shows the source comparison below the checklist, not behind a tab", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    await openDrawer(page);

    // Both are on screen at once — no switching, nothing hidden.
    await expect(items(page)).toHaveCount(3);
    await expect(page.locator(".people-by-source")).toBeVisible();
    await expect(page.locator(".review-sidebar__section-title")).toContainText(
      "Since last scrape",
    );

    // The tints have to agree with the checklist above them: Carol is the extra
    // official and reads as added, Dave the dropped one and reads as dropped.
    // Alice is on both sides and gets nothing.
    const rowFor = (name) =>
      page.locator(".people-by-source tbody tr").filter({ hasText: name });
    await expect(rowFor("Carol Extra")).toHaveClass(/people-by-source__row--added/);
    await expect(rowFor("Dave Absent")).toHaveClass(/people-by-source__row--dropped/);
    await expect(rowFor("Alice Mayor")).toHaveClass(/^$/);
  });

  // This fixture has no origin_source, so the collector never had a previous
  // scrape to compare against — the table is a first capture and says so.
  test("says what the baseline is when there was no previous scrape", async ({
    authenticatedPage: page,
  }) => {
    await openMarkers(page);
    await openDrawer(page);

    await expect(page.locator(".review-sidebar__note")).toContainText(
      "No previous scrape",
    );
    await expect(page.locator(".people-by-source thead")).toContainText(
      "Research",
    );
    await expect(page.locator(".people-by-source thead")).toContainText(
      "This scrape",
    );
  });
});
