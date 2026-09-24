/**
 * User story: reviewer opens a card whose pull request is already merged
 *
 * Given a card that has already been published
 * When I open it by link
 * Then I see it is merged, and can reach the pull request and the jurisdiction
 * And none of the actions that would change it are offered
 *
 * Every other fixture is an open PR with no url, so this is the only card that
 * exercises the terminal-status banner, the outbound links, and the read-only
 * gate on the session actions.
 */

import { test, expect } from "../fixtures/index.js";
import {
  READ_ONLY_CHANGESET_ID,
  READ_ONLY_PR_URL,
  READ_ONLY_WEBSITE_URL,
} from "../fixtures/db.js";
import { openEditorFor } from "./helpers/review-card.js";

test.describe("Review card — read only", () => {
  test("a published card shows its status and hides the actions that would change it", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${READ_ONLY_CHANGESET_ID}`);

    const banner = page.locator(".review-session__status-banner");
    await expect(banner).toBeVisible();
    // The banner is `--${reviewStatus}`, and a changeset's terminal state is published — the
    // vocabulary moved off the PR when the review stopped being one.
    await expect(banner).toHaveClass(/review-session__status-banner--published/);
    await expect(banner).toContainText("published");

    // Nothing here can be published, saved or closed again.
    await expect(page.locator(".review-session__approve-btn")).toHaveCount(0);
    await expect(page.locator(".review-session__save-btn")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Reject" })).toHaveCount(0);
  });

  test("a published card links out to the published data and the jurisdiction", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${READ_ONLY_CHANGESET_ID}`);

    const jurisdictionLink = page.locator(".review-session__jurisdiction");
    await expect(jurisdictionLink).toContainText("E2E Read Only City");

    await expect(page.locator(".review-session__jurisdiction-website")).toHaveAttribute(
      "href",
      READ_ONLY_WEBSITE_URL,
    );

    // "View published data", not "View PR": the url is where the change landed, which is a
    // commit or a pull request depending on the path it took.
    await expect(
      page.getByRole("link", { name: /View published data/ }),
    ).toHaveAttribute("href", READ_ONLY_PR_URL);
  });
});

test.describe("Review card — read only across the views", () => {
  const openReadOnly = async (page) => {
    await page.goto(`/review/session?changeset_id=${READ_ONLY_CHANGESET_ID}`);
    await expect(page.locator("review-overview")).toBeVisible();
  };

  test("the roster and what it published both stay readable — it is a historical record", async ({
    authenticatedPage: page,
  }) => {
    await openReadOnly(page);
    // This verified the overview and `<review-preview>` both rendered. The preview element
    // went in the 2026-09 redesign — the overview is the roster now — so what is left to
    // verify is that a published card still shows its roster rather than an empty shell.
    // As a fold, not a row: nothing changed on a published card, so every person is unchanged
    // and the collapse rule shows them in a strip.
    await expect(page.locator("review-overview")).toBeVisible();
    await expect(page.locator("review-overview .review-fold")).not.toHaveCount(0);
  });

  test("every field renders as its value, never a disabled input", async ({
    authenticatedPage: page,
  }) => {
    await openReadOnly(page);
    await openEditorFor(page, "Jane Published");

    const editor = page.locator(".person-editor").filter({ hasText: "Jane Published" });
    await editor.locator(".person-editor__expander").click();

    await expect(editor.locator("input")).toHaveCount(0);
    await expect(editor.locator("select")).toHaveCount(0);

    // The photo is shown as a photo — displayScalar would have printed its URL.
    await expect(editor.locator("person-image")).not.toHaveCount(0);
    await expect(
      editor.locator(".person-editor__field").filter({ hasText: "Email" }),
    ).toContainText("jane@ri.gov");
  });

  test("no mutating control is offered on any view", async ({
    authenticatedPage: page,
  }) => {
    await openReadOnly(page);
    // Overview: no way to add someone to a published card.
    await expect(page.locator("review-overview .review-row--ghost")).toHaveCount(0);

    await openEditorFor(page, "Jane Published");
    for (const control of [
      ".person-editor__delete",
      ".person-editor__reset",
      ".person-editor__restore-person",
      ".person-editor__restore",
      ".person-editor--ghost",
      // Adding a value is the trailing empty row, not a button — read-only
      // renders values as text, so there is no row to type into.
      ".field-control__input--draft",
    ]) {
      await expect(page.locator(control)).toHaveCount(0);
    }
  });

  // Retired 2026-09-23: "the modal opens and navigates, but offers nothing to undo". Opening a
  // person no longer opens `<review-modal>` — it is the merge screen now — and the claim it
  // made is covered above by "no mutating control is offered on any view", which asserts the
  // absence directly rather than through the modal's chrome.
});
