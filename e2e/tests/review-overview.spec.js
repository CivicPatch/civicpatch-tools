/**
 * Overview (2026-07-30 spec) — triage a whole card at a glance, at ?view=overview.
 *
 * One roster in seat order: status is carried by the card, so position is free.
 * The collapse rule decides what a card says and `status` decides how it looks —
 * both shared with the editor, so these assert the views agree rather than
 * re-testing the model.
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_CHANGESET_ID } from "../fixtures/db.js";

const openOverview = async (page, changesetId = SCALE_CHANGESET_ID) => {
  await page.goto(`/review/session?changeset_id=${changesetId}&view=overview`);
  await expect(page.locator("review-overview")).toBeVisible();
};

const rowFor = (page, name) =>
  page
    .locator(".review-row")
    .filter({ has: page.locator(".review-row__name", { hasText: name }) });

const foldFor = (page, name) =>
  page
    .locator(".review-fold")
    .filter({ has: page.locator(".review-fold__name", { hasText: name }) });

test.describe("Review overview", () => {
  test("renders one roster in seat order, folding the untouched", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    // 10 changed + 5 added + 3 the scrape dropped = 18 cards; the other 25 fold.
    //
    // This replaced a two-group assertion (counts "18"/"25", 25 faces in a strip).
    // The groups are gone: grouping moved people to express status, and now the
    // card expresses it, so seat order survives instead.
    await expect(page.locator(".review-row:not(.review-row--ghost)")).toHaveCount(18);
    await expect(page.locator(".review-fold")).toHaveCount(25);

    // An untouched person is still present and still theirs to open — folded, not
    // dropped from the list.
    await expect(foldFor(page, "Councillor 03 Scale")).toHaveCount(1);
    await expect(rowFor(page, "Councillor 03 Scale")).toHaveCount(0);
  });

  test("roster rank order is kept, so a fold sits between the cards around it", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    const names = (
      await page.locator(".review-row__name, .review-fold__name").allTextContents()
    ).map((n) => n.trim());

    // `sort_people` ranks by role before division, so the five the scrape promoted to
    // Council President head the list — a promotion moves someone, and the review shows
    // them where the roster will.
    expect(names.slice(0, 5)).toEqual([
      "Councillor 09 Scale",
      "Councillor 18 Scale",
      "Councillor 21 Scale",
      "Councillor 30 Scale",
      "Councillor 33 Scale",
    ]);

    // Then the council members, in ward order: W1 folds, W2 changed, W3 and W4 fold,
    // W5 changed. Reading that run top to bottom must give it back — this is the whole
    // point of dropping the groups.
    const start = names.indexOf("Councillor 01 Scale");
    expect(names.slice(start, start + 5)).toEqual([
      "Councillor 01 Scale",
      "Councillor 02 Scale",
      "Councillor 03 Scale",
      "Councillor 04 Scale",
      "Councillor 05 Scale",
    ]);
  });

  test("a card names the fields that moved, not just that something did", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    // Ranked: contact details ahead of term dates. Source urls is no longer in
    // this list — it is a context field and renders as a numbered link instead,
    // so a tag would say the same thing twice.
    const row = rowFor(page, "Councillor 02 Scale");
    await expect(row.locator(".review-row__field")).toHaveText(["Phone", "Term end"]);
    await expect(row).toHaveClass(/review-row--changed/);
    await expect(row.locator(".review-row__source")).toHaveCount(1);
  });

  test("the status is named in words, not carried by colour alone", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    // `removed` and `deleted` share a hue, so the badge is the only thing that
    // separates them — and nothing else names the status now the groups are gone.
    await expect(
      rowFor(page, "Councillor 02 Scale").locator(".review-row__badge"),
    ).toHaveText("Changed");
    await expect(
      rowFor(page, "Councillor 36 Scale").locator(".review-row__badge"),
    ).toHaveText("Not in scrape");
    await expect(
      rowFor(page, "Newcomer 01 Scale").locator(".review-row__badge"),
    ).toHaveText("New");
  });

  test("an issue outranks the field's own state", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    // Councillor 09 carries duplicate_unique_role, anchored to post_id. The
    // issue colours the field it is anchored to, ahead of that field's own diff
    // state — and the card says so once more in its own chip.
    const row = rowFor(page, "Councillor 09 Scale");
    const seat = row.locator(".review-row__field").filter({ hasText: "Post" });
    await expect(seat).toHaveClass(/review-row__field--issue/);
    await expect(row.locator(".review-row__attn")).toContainText("Has an issue");
  });

  test("a departing person is one decision — struck, and no field list", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    const row = rowFor(page, "Councillor 36 Scale");
    await expect(row).toHaveClass(/review-row--removed/);
    // With no new-side record every field reads cleared; a list here would say
    // "9 things to review" about a card that is one decision.
    await expect(row.locator(".review-row__field")).toHaveCount(0);
  });

  test("the add-person ghost is the last thing in the list", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    // This replaced "ends the To review group". There is no group to end: the
    // ghost is last overall, so adding someone puts their card where it stood and
    // pushes it down, and the affordance never moves.
    const list = page.locator(".review-overview__list");
    await expect(list.locator(".review-row--ghost")).toHaveCount(1);
    await expect(list.locator("> *").last()).toHaveClass(/review-row--ghost/);
  });

  test("a card opens the editor on that person", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    await rowFor(page, "Councillor 02 Scale").locator(".review-row__open").click();
    await expect(page.locator("review-modal dialog")).toBeVisible();
    await expect(page.locator(".review-modal__head")).toContainText("Councillor 02 Scale");
  });

  test("a folded person opens the editor too", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    // Folding is a display decision, not a loss of reach: an untouched person is
    // still editable, and the fold is the only way to get to them here.
    await foldFor(page, "Councillor 03 Scale").locator(".review-fold__open").click();
    await expect(page.locator("review-modal dialog")).toBeVisible();
    await expect(page.locator(".review-modal__head")).toContainText("Councillor 03 Scale");
  });

  test("the whole card is one target — nothing in it opens something else", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);

    // This replaced "a field name opens the editor focused on that field". Field
    // names used to be buttons; anything interactive in the meta row sits above
    // the card's hit area and punches holes in it, so the card was left with dead
    // zones between the tags. They are plain text now and the card opens focused
    // on its first ranked field either way.
    //
    // Source numbers are the one deliberate exception, raised above the hit area
    // so a reviewer can check a source without opening the person.
    const row = rowFor(page, "Councillor 02 Scale");
    await expect(row.locator(".review-row__meta button")).toHaveCount(0);
    await expect(
      row.locator(".review-row__meta a:not(.review-row__source)"),
    ).toHaveCount(0);

    // Clicking where a tag sits still opens the person: the card's hit area covers
    // it. A locator click would hang here — playwright waits for the tag itself to
    // receive the pointer, and the card is deliberately on top — so this clicks the
    // point, the way a reviewer does.
    // Scrolled first: `boundingBox` reports viewport coordinates and does not scroll, so on a
    // roster this long the click would land on whatever happens to be at that point instead.
    await row.scrollIntoViewIfNeeded();
    const tag = await row
      .locator(".review-row__field", { hasText: "Term end" })
      .boundingBox();
    await page.mouse.click(tag.x + tag.width / 2, tag.y + tag.height / 2);
    await expect(page.locator("review-modal dialog")).toBeVisible();
    await expect(page.locator(".review-modal__head")).toContainText("Councillor 02 Scale");
  });

  test("adding a person lands them last and opens the editor on them", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);
    const before = await page.locator(".review-row:not(.review-row--ghost)").count();

    await page.locator(".review-row--ghost").click();

    // A new person is empty, so the reviewer is put where they can fill them in
    // rather than left looking at a blank card. This needs the modal to open as
    // part of a re-render, which is the case civ-modal used to lose.
    await expect(page.locator("dialog[open]")).toHaveCount(1);
    await expect(page.locator(".review-modal__head")).toContainText("(unnamed)");
    await page.keyboard.press("Escape");
    await expect(page.locator("dialog[open]")).toHaveCount(0);

    // Appended, not prepended: they belong after the roster, where the add
    // affordance stood. Not *last* overall, though — departing people have no slot
    // and trail everything (see buildReviewCards), so the new person is the last of
    // the people still on the roster.
    await expect(page.locator(".review-row:not(.review-row--ghost)")).toHaveCount(before + 1);
    const staying =
      ".review-row:not(.review-row--ghost):not(.review-row--removed):not(.review-row--deleted)";
    await expect(page.locator(`${staying} .review-row__name`).last()).toHaveText("(unnamed)");
  });

  test("switching view writes ?view= so a refresh lands back there", async ({
    authenticatedPage: page,
  }) => {
    await openOverview(page);
    await page.locator(".review-page__view-tab", { hasText: "Detail" }).click();
    await expect(page).toHaveURL(/view=detail/);
  });
});
