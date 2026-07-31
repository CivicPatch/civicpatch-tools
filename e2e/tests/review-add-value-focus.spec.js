/**
 * User story: adding a value leaves the caret in it.
 *
 * Given a person's multi-value field
 * When I click its add button
 * Then a new empty chip appears
 * And the caret is already in it, so I can type
 *
 * Worth a test rather than an eyeball: the input being focused does not exist
 * when the click handler runs. `setValues` goes through the save round-trip and
 * the list re-renders afterwards, so the focus has to wait a frame and find the
 * new input by position. Nothing in a unit test can observe that, and a silent
 * regression turns one gesture back into two.
 */

import { test, expect } from "../fixtures/index.js";
import { RECONCILE_REQUEST_ID } from "../fixtures/db.js";
import { openDetail, railFor, fieldIn } from "./helpers/review-card.js";

test.describe("Adding a multi-value entry", () => {
  test("puts the caret in the chip it just created", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?request_id=${RECONCILE_REQUEST_ID}`);
    await openDetail(page);

    const emails = fieldIn(railFor(page, "Maria González"), "Email");
    const chipInputs = emails.locator(".field-control__chip input");
    const before = await chipInputs.count();

    await emails.locator(".field-control__add").click();

    await expect(chipInputs).toHaveCount(before + 1);

    // The new chip is the last one, and it is the one holding focus.
    const added = chipInputs.last();
    await expect(added).toBeFocused();
    await expect(added).toHaveValue("");

    // And it is genuinely typeable without a second click.
    await page.keyboard.type("new.address@example.gov");
    await expect(added).toHaveValue("new.address@example.gov");
  });
});
