/**
 * The gate on approving a card: a blocking error stops it, and says what to fix.
 *
 * This is what survives `review-preview.spec.js`, deleted on 2026-09-23. That file opened
 * `<review-preview>`, an element the 2026-09 redesign removed — the overview shows the roster
 * now, and `review-overview.spec.js` covers it. The gate outlived the preview because it was
 * never about it: §9 drives the button from `blockingErrors`, the same function the roster
 * editor's Publish uses.
 *
 * The blockers banner went with the preview, so the button carries the whole answer: its label
 * counts what is wrong and its title names it. One control, one source — which is what the
 * retired "the banner and the button agree" test was really asserting.
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_CHANGESET_ID } from "../fixtures/db.js";
import { openEditorFor, editorFor, actionsFor, fieldIn } from "./helpers/review-card.js";

const clearNameOf = async (page, name) => {
  await openEditorFor(page, name);
  const editor = editorFor(page, name);
  await editor.locator(".person-editor__expander").click();
  await fieldIn(editor, "Name").first().locator("input").fill("");
};

test.describe("Publish gating", () => {
  test("a blocking error disables Approve and says what to fix", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${SCALE_CHANGESET_ID}`);
    await clearNameOf(page, "Councillor 02 Scale");

    const approve = page.locator(".review-session__approve-btn");
    await expect(approve).toBeDisabled();
    await expect(approve).toContainText("to fix before approving");
    // Which field, not just how many: the banner used to say this, and the title says it now.
    await expect(approve).toHaveAttribute("title", /Name: Required/);

    // Save updates is never gated — parking incomplete work is what it is for.
    await expect(page.locator(".review-session__save-btn")).toBeEnabled();
  });

  test("a blocker on someone being dropped does not gate publishing", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${SCALE_CHANGESET_ID}`);
    // Name, because it is the only required scalar: clearing one row of Source urls leaves an
    // empty string rather than an empty list, and the Post field is a picker that cannot be
    // emptied into an error while the derivation still names a post.
    await clearNameOf(page, "Councillor 02 Scale");
    await expect(page.locator(".review-session__approve-btn")).toBeDisabled();

    // The card is findable by the fallback the editor renders once the name is gone, which is
    // what lets the name be the blocker here at all.
    await actionsFor(page, "(unnamed)").locator(".person-editor__delete").click();
    await expect(page.locator(".review-session__approve-btn")).toBeEnabled();
  });
});
