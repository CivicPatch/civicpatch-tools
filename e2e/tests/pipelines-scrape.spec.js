/**
 * User story: an admin starts a state's scrape from the pipelines page
 *
 * Given I am an admin on /pipelines
 * When I press a state's "Scrape now"
 * Then nothing starts until I confirm, because a batch spends money and cannot be recalled
 * And confirming posts that state to the batch endpoint
 * But anyone below admin is sent away from the page
 *
 * Moved here from `changeset-summaries.spec.js` when the trigger moved pages. Starting a scrape
 * is stubbed --- it reaches Temporal, which the e2e stack has no credentials for --- so this
 * tests the client wiring only. The stub is a hand-written copy of the endpoint's shape, so it
 * cannot catch the backend changing that shape. Not ported: "a state already scraping cannot
 * be started again", since this page has no per-state busy lock; the workflow id
 * (`state-scrape-{state}`, FAIL on conflict) is the only guard now.
 */

import { test, expect } from "../fixtures/index.js";

const PAGE = "/pipelines";
const BATCH = "**/api/v1/pipeline_runs/batch";

test("a maintainer is sent away from the pipelines page", async ({ maintainerPage: page }) => {
  await page.goto(PAGE);

  await expect(page).not.toHaveURL(/\/pipelines/);
});

test("an admin must confirm before a scrape starts", async ({ adminPage: page }) => {
  let posted = null;
  await page.route(BATCH, async (route) => {
    posted = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: { workflow_id: "state-scrape-e2e", state: posted.state } }),
    });
  });

  await page.goto(PAGE);
  const row = page.locator(".pipelines-page__row:not(.pipelines-page__row--head)").first();
  await expect(row).toBeVisible();
  const state = (await row.locator(".pipelines-page__row-state").textContent()).trim();

  await row.getByRole("button", { name: "Scrape now" }).click();
  expect(posted).toBeNull();

  await page.getByRole("button", { name: /start scraping/i }).click();
  await expect.poll(() => posted).not.toBeNull();
  expect(posted.state).toBe(state);
});
