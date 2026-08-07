/**
 * Locators for the review card's views.
 *
 * The card opens on Overview (§1.1), which is read-only by design — editing a
 * field means going to Detail first. Specs that only need "make this card dirty"
 * use editField; specs about a particular view address it directly.
 *
 * Not a spec file, so Playwright's testMatch never picks it up.
 */

import { expect } from "@playwright/test";

/** Switch to Detail via the tab a reviewer would use. */
export async function openDetail(page) {
  await page.locator(".review-page__view-tab", { hasText: "Detail" }).click();
  await expect(page.locator("person-editor-list")).toBeVisible();
}

export async function openOverview(page) {
  await page.locator(".review-page__view-tab", { hasText: "Overview" }).click();
  await expect(page.locator("review-overview")).toBeVisible();
}

/**
 * One person's editor, matched on their name header — a name can also appear in
 * another card's picker, which a bare hasText would happily match.
 */
export const editorFor = (page, name) =>
  page
    .locator(".person-editor")
    .filter({ has: page.locator(".person-editor__name", { hasText: name }) });

/** One person's Overview card, matched the same way. */
export const rowFor = (page, name) =>
  page
    .locator(".review-row")
    .filter({ has: page.locator(".review-row__name", { hasText: name }) });

/** An untouched person, who folds to a compact row rather than a card. */
export const foldFor = (page, name) =>
  page
    .locator(".review-fold")
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
  await openDetail(page);
  const editor = editorFor(page, name);
  const expander = editor.locator(".person-editor__expander");
  if (await fieldIn(editor, label).count() === 0) await expander.click();
  await fieldIn(editor, label).first().locator("input").first().fill(value);
}
