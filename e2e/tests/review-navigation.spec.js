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
    // State is pre-set to 'ca' via localStorage in the authenticatedPage fixture
    await page.goto("/review");

    // Wait for the review landing to render with available cards
    const startButton = page.locator(".review-page__start-btn");
    await expect(startButton).toBeVisible();
    await expect(startButton).toBeEnabled();

    await startButton.click();

    // After starting, the review session navigates to the first card.
    // The jurisdiction name should appear once the card loads.
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");
  });

  test("reviewer sees proposed people on first card", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

    // The seeded proposed person should appear in the diff panel
    await expect(page.locator("review-overview").getByText("Jane Smith").first()).toBeVisible();
  });

  test("next advances to second card", async ({ authenticatedPage: page }) => {
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

    await page.locator(".review-page__next-btn").click();

    await expect(page.locator(".review-page__progress")).toContainText("2");
  });

  test("back returns to previous card after next", async ({ authenticatedPage: page }) => {
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

    await page.locator(".review-page__next-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("2");

    await page.locator(".review-page__back-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("1");
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");
  });
});
