/**
 * The edit modal (spec §6) — the Detail editor mounted with one person.
 *
 * Opened from Overview, because Detail's fields are already editable inline.
 * What is worth asserting here is the behaviour around the editor rather than the
 * editor itself: which set it walks, that edits apply live, and that Revert undoes
 * only the person in view.
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_CHANGESET_ID } from "../fixtures/db.js";
import { openOverview, rowFor, editorFor, fieldIn } from "./helpers/review-card.js";

const openCardModal = async (page, name) => {
  await page.goto(`/review/session?changeset_id=${SCALE_CHANGESET_ID}`);
  await expect(page.locator("review-overview")).toBeVisible();
  await rowFor(page, name).locator(".review-row__open").click();
  await expect(page.locator("review-modal dialog")).toBeVisible();
};

// By accessible name, not by row: `hasText` is a case-insensitive *substring*
// match, so filtering rows on "Name" also catches "Other names" and the input
// lookup resolves to two.
const modalNameInput = (page) =>
  page.locator("review-modal").getByLabel("Name", { exact: true });

// Name is unchanged on these people, so the collapse rule hides it. Reaching a
// field that did not move is exactly what the expander is for — and expansion is
// keyed per person, so stepping to someone else starts collapsed again.
const showAllFields = (page) =>
  page.locator("review-modal .person-editor__expander").click();

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

  test("collapses by the same rule as the editor", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    const fields = page.locator("review-modal .person-editor__field");

    // The modal is the editor mounted with one person, not a second editor, so it
    // collapses rather than having its own idea of what to show: the two fields
    // that moved plus the always-visible Source urls. Opening with every field
    // is reserved for adding a person, who has nothing to collapse.
    await expect(fields).toHaveCount(3);

    await showAllFields(page);
    await expect(fields).toHaveCount(10);
  });

  test("Prev / Next move through the set in the order the roster is listed", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    // The walk order is the roster's own, so stepping through the modal matches
    // the list you opened it from rather than a status-sorted sequence. The
    // overview is still mounted behind the modal, so it can be read here.
    const rosterNames = (
      await page.locator(".review-row__name").allTextContents()
    ).map((n) => n.trim());
    // Derived, not hardcoded: the roster sorts by role rank before division, so who is first
    // depends on who the scrape promoted. The claim is that the walk follows that order.
    const at = rosterNames.indexOf("Councillor 02 Scale") + 1;
    await expect(page.locator(".review-modal__pos")).toContainText(`${at} of 18`);

    await page.locator('.review-modal__nav-btn[title*="Next"]').click();
    await expect(page.locator(".review-modal__pos")).toContainText(`${at + 1} of 18`);
    await expect(page.locator(".review-modal__person--on")).toContainText(rosterNames[at]);

    await page.locator('.review-modal__nav-btn[title*="Previous"]').click();
    await expect(page.locator(".review-modal__pos")).toContainText(`${at} of 18`);
    await expect(page.locator(".review-modal__person--on")).toContainText(rosterNames[at - 1]);
  });

  test("edits apply live and survive closing — Done keeps, it does not commit", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    await showAllFields(page);
    await modalNameInput(page).fill("Renamed Councillor");

    await page.locator("review-modal").getByText("Done").click();
    await expect(page.locator("review-modal dialog")).toHaveCount(0);

    // Overview already reflects it: the modal edits the same state Detail does.
    await expect(rowFor(page, "Renamed Councillor")).toBeVisible();
  });

  test("Revert undoes this person's edits", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    await showAllFields(page);
    const revert = page.locator(".review-modal__revert");

    // Nothing to undo yet — offered as disabled rather than as a silent no-op.
    await expect(revert).toBeDisabled();

    await modalNameInput(page).fill("Renamed Councillor");
    await expect(revert).toBeEnabled();

    await revert.click();
    await expect(modalNameInput(page)).toHaveValue("Councillor 02 Scale");
    await expect(revert).toBeDisabled();
  });

  test("Revert reaches the person in view and no one else", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    await showAllFields(page);
    await modalNameInput(page).fill("Edited First");

    // Move on, edit someone else, then revert them.
    await page.locator('.review-modal__nav-btn[title*="Next"]').click();
    await showAllFields(page);
    await modalNameInput(page).fill("Edited Second");
    await page.locator(".review-modal__revert").click();

    // The second person is back; the first person's edit is untouched — Revert
    // resets the person in view, not the session (§6.1).
    await expect(modalNameInput(page)).toHaveValue("Councillor 05 Scale");
    await page.locator('.review-modal__nav-btn[title*="Previous"]').click();
    await expect(modalNameInput(page)).toHaveValue("Edited First");
  });

  test("Revert restores a deletion made inside the modal, not just values", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    await page.locator("review-modal .person-editor__delete").click();
    await expect(page.locator("review-modal .person-editor")).toHaveClass(/person-editor--deleted/);

    // Restoring values while leaving the flag set is §12's impossible state, so
    // Revert clears both.
    await page.locator(".review-modal__revert").click();
    await expect(page.locator("review-modal .person-editor")).not.toHaveClass(/person-editor--deleted/);
  });

  test("Revert survives closing and reopening, as long as the roster reads dirty", async ({
    authenticatedPage: page,
  }) => {
    await openCardModal(page, "Councillor 02 Scale");
    await showAllFields(page);
    await modalNameInput(page).fill("Renamed Councillor");
    await page.locator("review-modal").getByText("Done").click();
    await expect(page.locator("review-modal dialog")).toHaveCount(0);

    // Revert measures against the card as it loaded, the same baseline that
    // marks the row dirty — not against the state the modal last opened in.
    await rowFor(page, "Renamed Councillor").locator(".review-row__open").click();
    await expect(page.locator("review-modal dialog")).toBeVisible();
    await showAllFields(page);
    await expect(page.locator(".review-modal__revert")).toBeEnabled();

    await page.locator(".review-modal__revert").click();
    await expect(modalNameInput(page)).toHaveValue("Councillor 02 Scale");
  });
});
