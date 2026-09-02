/**
 * Locators for the review card's views.
 *
 * The card opens on Overview (§1.1), which is read-only by design — editing a
 * field means opening that person's modal. Specs that only need "make this card
 * dirty" use editField; specs about a particular view address it directly.
 *
 * Not a spec file, so Playwright's testMatch never picks it up.
 */

import { expect } from "@playwright/test";

/**
 * Open one person's editor, the way a reviewer does: from their Overview entry.
 *
 * Someone with nothing to review folds to a compact strip rather than a row, so the
 * opener is on whichever of the two they rendered as.
 */
export async function openEditorFor(page, name) {
  const row = rowFor(page, name);
  const opener = (await row.count())
    ? row.locator(".review-row__open")
    : foldFor(page, name).locator(".review-fold__open");
  await opener.first().click();
  await expect(page.locator("review-modal dialog")).toBeVisible();
}

/**
 * Switch the open modal to another person, via its own list — which is how a reviewer
 * moves between people now that the Detail list is gone.
 */
export async function showPerson(page, name) {
  await page
    .locator(".review-modal__person")
    .filter({ has: page.locator(".review-modal__person-name", { hasText: name }) })
    .first()
    .click();
  await expect(page.locator(".review-modal__head")).toContainText(name);
}

/** Back to the roster from an open modal. There are no view tabs — the card is one page. */
export async function openOverview(page) {
  await page.keyboard.press("Escape");
  await expect(page.locator("review-overview")).toBeVisible();
}

/** The open modal, when it is showing this person — the head is what names them. */
const modalFor = (page, name) =>
  page
    .locator("review-modal dialog")
    .filter({ has: page.locator(".review-modal__who", { hasText: name }) });

/**
 * One person's editor, matched through the modal head that names them — a name can
 * also appear in another card's picker, which a bare hasText would happily match.
 *
 * Keyed on the head rather than on `.person-editor__name`: since the two heads merged,
 * only the *collapsed* strip still carries that class, so an expanded editor matched
 * nothing. The modal shows one person at a time, and merge candidates render as
 * `.review-face`, so one `.person-editor` matches whether it is a strip or expanded.
 */
export const editorFor = (page, name) => modalFor(page, name).locator(".person-editor");

/**
 * One person's action buttons — Remove, Reset, Merge with…, Restore.
 *
 * Separate from `editorFor` because the head merge moved them: they render from
 * `renderPersonSummary`, which the modal head calls, so they sit beside the name rather
 * than inside `.person-editor`. The merge *faces* did not move — they stay in the editor.
 */
export const actionsFor = (page, name) =>
  modalFor(page, name).locator(".person-editor__actions");

/** One person's Overview card, matched the same way. */
export const rowFor = (page, name) =>
  page
    .locator("review-overview .review-row")
    .filter({ has: page.locator(".review-row__name", { hasText: name }) });

/** An untouched person, who folds to a compact row rather than a card. */
export const foldFor = (page, name) =>
  page
    .locator("review-overview .review-fold")
    .filter({ has: page.locator(".review-fold__name", { hasText: name }) });

/** A field row within a person editor, by its label. */
export const fieldIn = (editor, label) =>
  editor.locator(".person-editor__field").filter({ hasText: label });

/**
 * Type into one person's field, from wherever the card currently is. Collapsed
 * fields have to be expanded first — that is the collapse rule doing its job,
 * not an obstacle to route around.
 */
export async function editField(page, name, label, value) {
  await openEditorFor(page, name);
  const editor = editorFor(page, name);
  const expander = editor.locator(".person-editor__expander");
  if (await fieldIn(editor, label).count() === 0) await expander.click();
  await fieldIn(editor, label).first().locator("input").first().fill(value);
}
