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
  READ_ONLY_REQUEST_ID,
  READ_ONLY_PR_URL,
  READ_ONLY_WEBSITE_URL,
} from "../fixtures/db.js";

test.describe("Review card — read only", () => {
  test("a merged card shows its status and hides the actions that would change it", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${READ_ONLY_REQUEST_ID}`);

    const banner = page.locator(".review-page__status-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toHaveClass(/review-page__status-banner--merged/);
    await expect(banner).toContainText("merged");

    // Nothing here can be published, saved or closed again.
    await expect(page.locator(".review-page__approve-btn")).toHaveCount(0);
    await expect(page.locator(".review-page__save-btn")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Reject" })).toHaveCount(0);
  });

  test("a merged card links out to the pull request and the jurisdiction", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${READ_ONLY_REQUEST_ID}`);

    const jurisdictionLink = page.locator(".review-page__jurisdiction");
    await expect(jurisdictionLink).toContainText("E2E Read Only City");

    await expect(page.locator(".review-page__jurisdiction-website")).toHaveAttribute(
      "href",
      READ_ONLY_WEBSITE_URL,
    );

    await expect(page.getByRole("link", { name: /View PR/ })).toHaveAttribute(
      "href",
      READ_ONLY_PR_URL,
    );
  });
});

test.describe("Review card — read only across the views", () => {
  const openReadOnly = async (page) => {
    await page.goto(`/review/session?changeset_id=${READ_ONLY_REQUEST_ID}`);
    await expect(page.locator("review-overview")).toBeVisible();
  };

  test("all three views stay available — the card is a historical record", async ({
    authenticatedPage: page,
  }) => {
    await openReadOnly(page);
    await expect(page.locator(".review-page__view-tab")).toHaveCount(3);

    await page.locator(".review-page__view-tab", { hasText: "Detail" }).click();
    await expect(page.locator("person-editor-list")).toBeVisible();
    await page.locator(".review-page__view-tab", { hasText: "Preview" }).click();
    await expect(page.locator("review-preview")).toBeVisible();
  });

  test("every field renders as its value, never a disabled input", async ({
    authenticatedPage: page,
  }) => {
    await openReadOnly(page);
    await page.locator(".review-page__view-tab", { hasText: "Detail" }).click();

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
    await expect(page.locator(".review-row--ghost")).toHaveCount(0);

    await page.locator(".review-page__view-tab", { hasText: "Detail" }).click();
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

  test("the modal opens and navigates, but offers nothing to undo", async ({
    authenticatedPage: page,
  }) => {
    await openReadOnly(page);
    await page.locator(".review-row__open").first().click();
    await expect(page.locator("review-modal dialog")).toBeVisible();

    // Close, not Done — there is nothing to keep — and no Revert at all.
    await expect(page.locator(".review-modal__revert")).toHaveCount(0);
    await expect(page.locator("review-modal").getByText("Close")).toBeVisible();
  });
});
