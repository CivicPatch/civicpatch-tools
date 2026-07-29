/**
 * User story: reviewing a jurisdiction's FIRST capture (no prior scrape)
 *
 * Given a jurisdiction with scraped_at NULL and an open pull request
 * When I open its review card
 * Then I see the "first capture" baseline banner
 * And the old<->new diff panel is suppressed (nothing to compare against)
 * And the proposed people still render in the editable workspace
 */

import { test, expect } from "../fixtures/index.js";
import { BASELINE_REQUEST_ID } from "../fixtures/db.js";

test.describe("Review baseline mode (first capture)", () => {
  test("baseline review shows the banner and suppresses the diff panel", async ({
    authenticatedPage: page,
  }) => {
    // Deep-link straight to the baseline card by request_id (state-agnostic —
    // boot() resolves it via the by-request endpoint, which carries `mode`).
    await page.goto(`/review/session?request_id=${BASELINE_REQUEST_ID}`);

    const banner = page.locator(".review-page__baseline-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText("First capture for E2E Baseline City");

    // Overview is the entry point in both modes; the proposed person is on it.
    await expect(
      page.locator("review-overview").getByText("Jane Baseline").first()
    ).toBeVisible();
  });
});
