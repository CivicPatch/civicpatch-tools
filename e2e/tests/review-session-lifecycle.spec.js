/**
 * User story: reviewer session lifecycle
 *
 * These tests verify observable browser behavior — what the user sees and
 * can do — without caring about internal DB state or SQL.
 */

import { test, expect } from "../fixtures/index.js";
import { test as base } from "@playwright/test";

test.describe("Review session lifecycle", () => {
  test("end session returns to landing page", async ({ authenticatedPage: page }) => {
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

    await page.locator(".review-page__end-btn").click();

    // Should return to landing with the Review button available
    await expect(page.locator(".review-page__start-btn")).toBeVisible();
  });

  test("restarting a session after ending shows a card", async ({ authenticatedPage: page }) => {
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

    // End the session
    await page.locator(".review-page__end-btn").click();
    await expect(page.locator(".review-page__start-btn")).toBeVisible();

    // Start again — should show a card (session is fresh)
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");
  });

  test("session progress dots are visible during review", async ({ authenticatedPage: page }) => {
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

    // At least one dot should be rendered
    await expect(page.locator(".review-page__dot").first()).toBeVisible();

    // The current dot should be present
    await expect(page.locator(".review-page__dot--current")).toBeVisible();
  });

  test("direct link shows Exit button, not End session", async ({ authenticatedPage: page }) => {
    // Verified a deeplink on /review before; now verifies it on /review/session
    // because the route split moved deeplinks there. Deeplinks key off the
    // seeded PR's changeset_id.
    await page.goto("/review/session?changeset_id=00000000-0000-0000-eeee-000000000001");

    const endBtn = page.locator(".review-page__end-btn");
    await expect(endBtn).toBeVisible();
    await expect(endBtn).toHaveText("Exit");
  });

  test("direct link Exit button returns to landing", async ({ authenticatedPage: page }) => {
    // Deeplink moved to /review/session; Exit still returns to the /review landing.
    await page.goto("/review/session?changeset_id=00000000-0000-0000-eeee-000000000001");
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

    await page.locator(".review-page__end-btn").click();

    // Should show landing page (start review button or some landing indicator)
    await expect(page.locator(".review-page__start-btn")).toBeVisible();
  });

  test("refreshing mid-session resumes at the correct position", async ({ authenticatedPage: page }) => {
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

    // Advance to card 2 so the resume has a non-trivial position to restore
    await page.locator(".review-page__next-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("2");

    // Reload — session should resume at card 2, not restart at card 1
    await page.reload();
    await expect(page.locator(".review-page__progress")).toContainText("2");
    await expect(page.locator(".review-page__dot--current")).toBeVisible();
  });

  test("back button is disabled on first card", async ({ authenticatedPage: page }) => {
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

    // First card has no previous entry — Back must be disabled
    await expect(page.locator(".review-page__back-btn")).toBeDisabled();
  });

});

base.describe("Unauthenticated access", () => {
  test("review page does not crash without login", async ({ page }) => {
    const baseUrl = process.env.BASE_URL ?? "http://localhost:8100";
    await page.goto(`${baseUrl}/review`);

    // Renders a page (not a 500) and does not show the review start button
    await expect(page).not.toHaveURL(/error/);
    await expect(page.locator(".review-page__start-btn")).not.toBeVisible();
  });
});
