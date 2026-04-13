/**
 * User story: reviewer navigates a review session
 *
 * Given a jurisdiction exists with an open pull request
 * And I am logged in as a reviewer
 * When I start a review session for that state
 * Then I can navigate to the first card
 * And I can see the jurisdiction name and proposed people
 */

import { test, expect } from "../fixtures/index.js";

test.describe("Review navigation", () => {
  test("reviewer can start a session and navigate to first card", async ({
    authenticatedPage: page,
  }) => {
    // ?state=ca pre-populates the state selector without interacting with the web component
    await page.goto("/review?state=ca");

    // Wait for the review landing to render with available cards
    const startButton = page.locator(".review-page__start-btn");
    await expect(startButton).toBeVisible();
    await expect(startButton).toBeEnabled();

    await startButton.click();

    // After starting, the review session navigates to the first card.
    // The jurisdiction name should appear once the card loads.
    await expect(page.getByText("E2E Test City")).toBeVisible();
  });

  test("reviewer sees proposed people on first card", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/review?state=ca");
    await page.locator(".review-page__start-btn").click();
    await expect(page.getByText("E2E Test City")).toBeVisible();

    // The seeded proposed person should appear in the diff panel
    await expect(page.locator("civ-diff-panel").getByText("Jane Smith")).toBeVisible();
  });
});
