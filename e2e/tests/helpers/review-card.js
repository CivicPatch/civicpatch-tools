/**
 * Locators for the review card.
 *
 * The card is one roster of person cards. Clicking a card expands that person's editor
 * inline beneath it; only one is open at a time, and clicking the same card again closes
 * it. Specs that only need "make this card dirty" use editField; specs about a particular
 * part of the card address it directly.
 *
 * Not a spec file, so Playwright's testMatch never picks it up.
 */

import { expect } from "@playwright/test";

/** One person's Overview card, matched by the name it shows. */
export const rowFor = (page, name) =>
  page
    .locator("review-overview .rperson")
    .filter({ has: page.locator(".pc-name", { hasText: name }) });

/** An untouched person, who folds to a compact strip rather than a card. */
export const foldFor = (page, name) =>
  page
    .locator("review-overview .review-fold")
    .filter({ has: page.locator(".review-fold__name", { hasText: name }) });

/** A departing person past the first few, collapsed to a name chip. */
const chipFor = (page, name) =>
  page.locator("review-overview .review-overview__chip", { hasText: name });

// `.rperson__open` is pointer-events: none, so a card opens from a click on its content.
async function openerFor(page, name) {
  const row = rowFor(page, name);
  if (await row.count()) return row.first().locator(".pc-name");
  const fold = foldFor(page, name);
  if (await fold.count()) return fold.first().locator(".review-fold__open");
  return chipFor(page, name).first();
}

/**
 * The open inline editor, when it is showing this person. Keyed on the editor's own name
 * line: a name can also appear in a merge candidate's face, which a bare hasText would match.
 */
const inlineFor = (page, name) =>
  page
    .locator(".person-editor-inline")
    .filter({ has: page.locator(".person-editor__name", { hasText: name }) });

/** Open one person's editor, the way a reviewer does: from their Overview entry. */
export async function openEditorFor(page, name) {
  if (await inlineFor(page, name).count()) return;
  await (await openerFor(page, name)).click();
  await expect(inlineFor(page, name)).toBeVisible();
}

/** Move the editor to another person. Opening one closes whoever was open. */
export async function showPerson(page, name) {
  await openEditorFor(page, name);
}

/** Back to the roster: close whichever editor is open by clicking its card again. */
export async function openOverview(page) {
  const open = page.locator(".person-editor-inline");
  if (await open.count()) {
    const name = (await open.locator(".person-editor__name").first().textContent()).trim();
    await (await openerFor(page, name)).click();
  }
  await expect(open).toHaveCount(0);
  await expect(page.locator("review-overview")).toBeVisible();
}

/** One person's editor, whether it renders as a strip or expanded. */
export const editorFor = (page, name) => inlineFor(page, name).locator(".person-editor");

/**
 * One person's action buttons: Remove, Reset, Merge with..., Restore. They sit in the
 * editor's summary line, beside the status text, not inside `.person-editor`.
 */
export const actionsFor = (page, name) =>
  inlineFor(page, name).locator(".person-editor__actions");

/** A field row within a person editor, by its label. */
export const fieldIn = (editor, label) =>
  editor.locator(".person-editor__field").filter({ hasText: label });

/**
 * Type into one person's field, from wherever the card currently is. Collapsed
 * fields have to be expanded first: that is the collapse rule doing its job,
 * not an obstacle to route around.
 */
export async function editField(page, name, label, value) {
  await openEditorFor(page, name);
  const editor = editorFor(page, name);
  const expander = editor.locator(".person-editor__expander");
  if (await fieldIn(editor, label).count() === 0) await expander.click();
  await fieldIn(editor, label).first().locator("input").first().fill(value);

  // Renaming moves the editor off `name`, so close whatever is open rather than looking it up.
  await openOverview(page);
}
