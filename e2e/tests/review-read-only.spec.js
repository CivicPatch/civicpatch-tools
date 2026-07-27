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
    await page.goto(`/review/session?request_id=${READ_ONLY_REQUEST_ID}`);

    const banner = page.locator(".review-page__status-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toHaveClass(/review-page__status-banner--merged/);
    await expect(banner).toContainText("merged");

    // Nothing here can be published, saved or closed again.
    await expect(page.locator(".review-page__merge-btn")).toHaveCount(0);
    await expect(page.locator(".review-page__save-btn")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Close PR" })).toHaveCount(0);
  });

  test("a merged card links out to the pull request and the jurisdiction", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?request_id=${READ_ONLY_REQUEST_ID}`);

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
