/**
 * User story: reviewer jumps between cards using the progress dots
 *
 * Given I am in a review session with several cards
 * When I advance through cards and then click an earlier dot
 * Then I jump to that card
 * And the dots reflect where I have been: current, already-visited, not-yet-reached
 *
 * Back/Next are covered by review-navigation.spec.js. The dots are a separate
 * navigation path — they jump to an arbitrary entry rather than +/-1 — and carry
 * the only per-entry status rendering in the session controls.
 */

import { test, expect } from "../fixtures/index.js";

// NJ seeds three open pull requests, so a fresh session has three cards.
const SEEDED_NJ_CARDS = 3;

test.describe("Review progress dots", () => {
  test("dots for unreached cards are disabled on the first card", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

    const dots = page.locator(".review-page__dot");
    await expect(dots).toHaveCount(SEEDED_NJ_CARDS);

    // Card 1 is current (disabled — you are already there); 2 and 3 are unreached.
    await expect(dots.nth(0)).toBeDisabled();
    await expect(dots.nth(1)).toBeDisabled();
    await expect(dots.nth(2)).toBeDisabled();
  });

  test("clicking an earlier dot jumps back to that card", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

    await page.locator(".review-page__next-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("2");
    await page.locator(".review-page__next-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("3");

    // Jump straight back to card 1 — two steps back in a single click.
    await page.locator(".review-page__dot").nth(0).click();

    await expect(page.locator(".review-page__progress")).toContainText(
      `1 of ${SEEDED_NJ_CARDS}`,
    );
  });

  test("visited cards become reachable dots once passed", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/review");
    await page.locator(".review-page__start-btn").click();
    await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

    await page.locator(".review-page__next-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("2");
    await page.locator(".review-page__next-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("3");

    await page.locator(".review-page__dot").nth(0).click();
    await expect(page.locator(".review-page__progress")).toContainText("1 of");

    const dots = page.locator(".review-page__dot");

    // Card 1 is where we are now.
    await expect(dots.nth(0)).toHaveClass(/review-page__dot--current/);

    // Cards 2 and 3 were visited but neither published nor saved — they are
    // deferred, and clickable so the reviewer can return to them.
    await expect(dots.nth(1)).toHaveClass(/review-page__dot--deferred/);
    await expect(dots.nth(2)).toHaveClass(/review-page__dot--deferred/);
    await expect(dots.nth(1)).toBeEnabled();
    await expect(dots.nth(2)).toBeEnabled();
  });
});
