/**
 * User story: picking how much to review when only a few cards are waiting
 *
 * Given fewer cards are available than the smallest session length on offer
 * When I open the review landing
 * Then it offers exactly that many, already picked
 * And starting a review asks for that many, never an undefined length
 *
 * The seeded NJ queue holds fewer cards than the smallest fixed length.
 */

import { test, expect } from "../fixtures/index.js";

test("fewer cards than the smallest session: the one length offered is the one sent", async ({
  authenticatedPage: page,
}) => {
  await page.goto("/review");

  const chips = page.locator(".review-page__goal-chip");
  await expect(chips).toHaveCount(1);
  await expect(chips.first()).toHaveClass(/review-page__goal-chip--active/);
  await expect(chips.first()).toBeEnabled();
  const offered = Number((await chips.first().innerText()).trim());

  const created = page.waitForRequest(
    (request) => request.url().endsWith("/api/v1/review-sessions") && request.method() === "POST",
  );
  await page.locator(".review-page__start-btn").click();
  expect((await created).postDataJSON().session_length).toBe(offered);
});
