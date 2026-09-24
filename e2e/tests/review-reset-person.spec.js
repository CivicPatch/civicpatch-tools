/**
 * Reset — undoing one person's edits, in the editor the overview opens.
 *
 * This is what survives `review-modal.spec.js`, deleted on 2026-09-23. That file opened a
 * person in `<review-modal>`; the 2026-09 redesign made a tile open the *inline* editor
 * instead, and `<review-modal>` is now bound to `mergeAnchorId` — it is the merge screen, which
 * `review-merge-screen.spec.js` covers. The tests about the modal's own chrome (its header, its
 * person list, its Prev/Next) went with it: `review-dot-navigation.spec.js` and
 * `person-editor.spec.js` already cover stepping between people and how fields collapse.
 *
 * Reset outlived the modal because it was never about it. It measures against the card as it
 * loaded — the same baseline that marks a row dirty — and it reaches the person in view, not
 * the session (§6.1).
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_CHANGESET_ID } from "../fixtures/db.js";
import {
  rowFor,
  openEditorFor,
  showPerson,
  openOverview,
  editorFor,
  actionsFor,
} from "./helpers/review-card.js";

const FIRST = "Councillor 02 Scale";
const SECOND = "Councillor 05 Scale";

const open = async (page, name) => {
  await page.goto(`/review/session?changeset_id=${SCALE_CHANGESET_ID}`);
  await expect(page.locator("review-overview")).toBeVisible();
  await openEditorFor(page, name);
};

// Name is unchanged on these people, so the collapse rule hides it. Reaching a field that did
// not move is exactly what the expander is for — and expansion is keyed per person, so
// stepping to someone else starts collapsed again.
const showAllFields = (page, name) =>
  editorFor(page, name).locator(".person-editor__expander").click();

const nameInput = (page, name) =>
  editorFor(page, name).getByLabel("Name", { exact: true });

const reset = (page, name) => actionsFor(page, name).locator(".person-editor__reset");

test.describe("Reset one person's edits", () => {
  test("undoes this person's edits, and is offered only once there are some", async ({
    authenticatedPage: page,
  }) => {
    await open(page, FIRST);
    await showAllFields(page, FIRST);

    // This verified Reset was present but disabled. It now verifies it is absent until there
    // is something to undo, because `editor-props` passes no `onReset` for a clean person and
    // the editor renders the button only when it has one.
    await expect(reset(page, FIRST)).toHaveCount(0);

    await nameInput(page, FIRST).fill("Renamed Councillor");
    await expect(reset(page, "Renamed Councillor")).toBeVisible();

    await reset(page, "Renamed Councillor").click();
    await expect(nameInput(page, FIRST)).toHaveValue(FIRST);
    await expect(reset(page, FIRST)).toHaveCount(0);
  });

  test("reaches the person in view and no one else", async ({
    authenticatedPage: page,
  }) => {
    await open(page, FIRST);
    await showAllFields(page, FIRST);
    await nameInput(page, FIRST).fill("Edited First");

    await showPerson(page, SECOND);
    await showAllFields(page, SECOND);
    await nameInput(page, SECOND).fill("Edited Second");
    await reset(page, "Edited Second").click();

    await expect(nameInput(page, SECOND)).toHaveValue(SECOND);
    await showPerson(page, "Edited First");
    await expect(nameInput(page, "Edited First")).toHaveValue("Edited First");
  });

  test("restores a removal, not just values", async ({ authenticatedPage: page }) => {
    await open(page, FIRST);
    await actionsFor(page, FIRST).locator(".person-editor__delete").click();

    // Restoring values while leaving the row removed is §12's impossible state. A removed row
    // offers Restore rather than Reset, which is the same undo said in the departing voice.
    await expect(actionsFor(page, FIRST).locator(".person-editor__restore-person")).toBeVisible();
    await actionsFor(page, FIRST).locator(".person-editor__restore-person").click();
    await expect(actionsFor(page, FIRST).locator(".person-editor__delete")).toBeVisible();
  });

  test("survives closing and reopening, as long as the roster reads dirty", async ({
    authenticatedPage: page,
  }) => {
    await open(page, FIRST);
    await showAllFields(page, FIRST);
    await nameInput(page, FIRST).fill("Renamed Councillor");
    await openOverview(page);

    // Reset measures against the card as it loaded, the same baseline that marks the row
    // dirty — not against the state the editor last opened in.
    await rowFor(page, "Renamed Councillor").locator(".pc-name").click();
    await showAllFields(page, "Renamed Councillor");
    await reset(page, "Renamed Councillor").click();

    await expect(nameInput(page, FIRST)).toHaveValue(FIRST);
  });
});
