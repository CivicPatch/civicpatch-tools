/**
 * User story: the review header stays usable while working through a card
 *
 * Given I am reviewing a card
 * Then on a wide screen the nav and the actions sit on one sticky row
 * And on a narrow screen only the slim nav stays stuck, with the actions below it
 * And the header stays pinned as I scroll through a long list of people
 *
 * The header's stickiness depends on custom-element hosts dissolving with
 * `display: contents` so .review-page__header (wide) and .review-page__step-nav
 * (narrow) end up as direct flex items of .review-page. That is invisible to
 * markup assertions and to the DOM snapshot: nesting the header one level deeper
 * silently un-sticks it while every other test still passes.
 */

import { test, expect } from "../fixtures/index.js";

const NARROW_VIEWPORT = { width: 375, height: 800 };

async function openFirstCard(page) {
  await page.goto("/review");
  await page.locator(".review-page__start-btn").click();
  await expect(page.getByText("E2E Test City")).toBeVisible();
}

const positionOf = (page, selector) =>
  page.evaluate(
    (sel) => getComputedStyle(document.querySelector(sel)).position,
    selector,
  );

const displayOf = (page, selector) =>
  page.evaluate(
    (sel) => getComputedStyle(document.querySelector(sel)).display,
    selector,
  );

test.describe("Review header layout", () => {
  test("wide screens keep the nav and the actions on one sticky row", async ({
    authenticatedPage: page,
  }) => {
    await openFirstCard(page);

    expect(await positionOf(page, ".review-page__header")).toBe("sticky");

    const nav = await page.locator(".review-page__step-nav").boundingBox();
    const actions = await page.locator(".review-page__actions").boundingBox();

    // Same row: each one's vertical midpoint falls inside the other's box.
    const navMid = nav.y + nav.height / 2;
    const actionsMid = actions.y + actions.height / 2;
    expect(navMid).toBeGreaterThan(actions.y);
    expect(navMid).toBeLessThan(actions.y + actions.height);
    expect(actionsMid).toBeGreaterThan(nav.y);
    expect(actionsMid).toBeLessThan(nav.y + nav.height);
  });

  test("narrow screens dissolve the header and stick only the nav", async ({
    authenticatedPage: page,
  }) => {
    await page.setViewportSize(NARROW_VIEWPORT);
    await openFirstCard(page);

    // The header stops being a box so the nav and actions become siblings in
    // the page's own flex flow.
    expect(await displayOf(page, ".review-page__header")).toBe("contents");
    expect(await positionOf(page, ".review-page__step-nav")).toBe("sticky");

    const nav = await page.locator(".review-page__step-nav").boundingBox();
    const actions = await page.locator(".review-page__actions").boundingBox();

    // Actions drop below the nav rather than sharing its row.
    expect(actions.y).toBeGreaterThanOrEqual(nav.y + nav.height);
  });

  test("the header stays pinned while scrolling a card", async ({
    authenticatedPage: page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 400 });
    await openFirstCard(page);

    const before = await page.locator(".review-page__header").boundingBox();
    await page.mouse.wheel(0, 600);

    const after = await page.locator(".review-page__header").boundingBox();
    // Pinned to the top of the viewport, not scrolled away with the content.
    expect(after.y).toBeLessThanOrEqual(before.y + 1);
    expect(after.y).toBeLessThan(10);
  });
});
