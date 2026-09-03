/**
 * Merge is the review modal's other screen, not a second dialog.
 */

import { test, expect } from "../fixtures/index.js";
import { RECONCILE_CHANGESET_ID } from "../fixtures/db.js";
import { actionsFor, openEditorFor, editorFor } from "./helpers/review-card.js";

test("merge is a screen in one modal, not a second dialog", async ({
  authenticatedPage: page,
}) => {
  await page.goto(`/review/session?changeset_id=${RECONCILE_CHANGESET_ID}`);
  await openEditorFor(page, "Tom Treasurer");

  const tom = editorFor(page, "Tom Treasurer");
  await actionsFor(page, "Tom Treasurer")
    .locator(".person-editor__merge")
    .click();
  await tom
    .locator(".person-editor__merge-faces .review-face", {
      hasText: "Bob Clerk",
    })
    .click();

  await expect(page.locator("merge-picker")).toBeVisible();
  // The whole point: one dialog, never two stacked.
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  // The footer is merge's while merging: its own actions, and none of the person
  // screen's. This asserted the footer was absent entirely, which was true when
  // merge drew its actions inline — they moved into the footer so they cannot
  // scroll out of reach.
  const foot = page.locator(".review-modal__foot");
  await expect(foot).toContainText("Merge into");
  await expect(foot).not.toContainText("Revert this person");
  await expect(foot).not.toContainText("Done");

  // Back returns to the person the merge started from — the modal never closed.
  await page.locator(".merge-picker__back").click();
  await expect(page.locator("merge-picker")).toHaveCount(0);
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  await expect(page.locator(".review-modal__head")).toContainText(
    "Tom Treasurer",
  );
  await expect(page.locator(".review-modal__foot")).toContainText("Done");
});
