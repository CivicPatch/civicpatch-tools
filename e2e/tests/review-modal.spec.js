/**
 * The edit modal (spec §6) — the Detail rail mounted with one person.
 *
 * Opened from Overview, because Detail's fields are already editable inline.
 * What is worth asserting here is the behaviour around the rail rather than the
 * rail itself: which set it walks, that edits apply live, and that Revert undoes
 * only the person in view.
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_REQUEST_ID } from "../fixtures/db.js";
import { openOverview, tileFor, railFor, fieldIn } from "./helpers/review-card.js";

const openCardModal = async (page, name) => {
  await page.goto(`/review/session?request_id=${SCALE_REQUEST_ID}`);
  await expect(page.locator("review-overview")).toBeVisible();
  await tileFor(page, name).locator(".review-tile__open").click();
  await expect(page.locator("review-modal dialog")).toBeVisible();
};

const modalField = (page, label) =>
  page.locator("review-modal .review-rail__field").filter({ hasText: label });

// Name is unchanged on these people, so the collapse rule hides it. Reaching a
// field that did not move is exactly what the expander is for — and expansion is
// keyed per person, so stepping to someone else starts collapsed again.
const showAllFields = (page) =>
  page.locator("review-modal .review-rail__expander").click();

test.describe("Review modal", () => {
  test("opens on the person whose tile was clicked", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    await expect(page.locator(".review-modal__head")).toContainText("Councillor 02 Scale");
    await expect(page.locator(".review-modal__pos")).toContainText("of 18");
  });

  test("walks the group it was opened from, not the whole card", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");

    // 18 need review; the 25 untouched people are a separate group. Stepping into
    // them would land on someone with no visible fields — a dead end (§6).
    await expect(page.locator(".review-modal__person")).toHaveCount(18);
    await expect(
      page.locator(".review-modal__person").filter({ hasText: "Councillor 03 Scale" }),
    ).toHaveCount(0);
  });

  test("collapses by the same rule as the rail", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    const fields = page.locator("review-modal .review-rail__field");

    // The modal is the rail mounted with one person, not a second editor, so it
    // collapses rather than having its own idea of what to show: the two fields
    // that moved plus the always-visible Source urls. Opening with every field
    // is reserved for adding a person, who has nothing to collapse.
    await expect(fields).toHaveCount(3);

    await showAllFields(page);
    await expect(fields).toHaveCount(11);
  });

  test("Prev / Next move through the set and the sidebar follows", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    await expect(page.locator(".review-modal__pos")).toContainText("3 of 18");

    await page.locator('.review-modal__nav-btn[title*="Next"]').click();
    await expect(page.locator(".review-modal__pos")).toContainText("4 of 18");
    await expect(page.locator(".review-modal__person--on")).toContainText("Councillor 05 Scale");

    await page.locator('.review-modal__nav-btn[title*="Previous"]').click();
    await expect(page.locator(".review-modal__pos")).toContainText("3 of 18");
  });

  test("edits apply live and survive closing — Done keeps, it does not commit", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    await showAllFields(page);
    await modalField(page, "Name").locator("input").fill("Renamed Councillor");

    await page.locator("review-modal").getByText("Done").click();
    await expect(page.locator("review-modal dialog")).toHaveCount(0);

    // Overview already reflects it: the modal edits the same state Detail does.
    await expect(tileFor(page, "Renamed Councillor")).toBeVisible();
  });

  test("Revert undoes this person, and only since the modal opened", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    await showAllFields(page);
    const revert = page.locator(".review-modal__revert");

    // Nothing to undo yet — offered as disabled rather than as a silent no-op.
    await expect(revert).toBeDisabled();

    await modalField(page, "Name").locator("input").fill("Renamed Councillor");
    await expect(revert).toBeEnabled();

    await revert.click();
    await expect(modalField(page, "Name").locator("input")).toHaveValue("Councillor 02 Scale");
    await expect(revert).toBeDisabled();
  });

  test("the snapshot is re-taken on each move, so Revert never reaches back", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    await showAllFields(page);
    await modalField(page, "Name").locator("input").fill("Edited First");

    // Move on, edit someone else, then revert them.
    await page.locator('.review-modal__nav-btn[title*="Next"]').click();
    await showAllFields(page);
    await modalField(page, "Name").locator("input").fill("Edited Second");
    await page.locator(".review-modal__revert").click();

    // The second person is back; the first person's edit is untouched — Revert is
    // an undo buffer for the person in view, not for the session (§6.1).
    await expect(modalField(page, "Name").locator("input")).toHaveValue("Councillor 05 Scale");
    await page.locator('.review-modal__nav-btn[title*="Previous"]').click();
    await expect(modalField(page, "Name").locator("input")).toHaveValue("Edited First");
  });

  test("Revert restores a deletion made inside the modal, not just values", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    await page.locator("review-modal .review-rail__delete").click();
    await expect(page.locator("review-modal .review-rail")).toHaveClass(/review-rail--deleted/);

    // Restoring values while leaving the flag set is §12's impossible state, so
    // the snapshot carries both.
    await page.locator(".review-modal__revert").click();
    await expect(page.locator("review-modal .review-rail")).not.toHaveClass(/review-rail--deleted/);
  });
});
