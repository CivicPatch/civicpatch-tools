/**
 * User story: an admin starts a pipeline's pass over a state from the pipelines page
 *
 * Given I am an admin on /pipelines
 * When I pick a pipeline and press a state's "Run now"
 * Then nothing starts until I confirm, because a batch spends money and cannot be recalled
 * And confirming posts that state to that pipeline's batch endpoint
 * But anyone below admin is sent away from the page
 *
 * Moved here from `changeset-summaries.spec.js` when the trigger moved pages. Starting a scrape
 * is stubbed --- it reaches Temporal, which the e2e stack has no credentials for --- so this
 * tests the client wiring only. The stub is a hand-written copy of the endpoint's shape, so it
 * cannot catch the backend changing that shape. Not ported: "a state already scraping cannot
 * be started again", since this page has no per-state busy lock; the workflow id
 * (`people-collector-state-{state}`, FAIL on conflict) is the only guard now.
 */

import { test, expect } from "../fixtures/index.js";

const PAGE = "/pipelines";
const BATCH = "**/api/v1/pipeline_runs/batch";
const LAW_BATCH = "**/api/v1/pipeline_runs/governing_law_collector/batch";

async function stubBatch(page, url) {
  const posted = { body: null };
  await page.route(url, async (route) => {
    posted.body = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: { workflow_id: "e2e", state: posted.body.state } }),
    });
  });
  return posted;
}

async function firstRow(page) {
  const row = page.locator(".pipelines-page__row:not(.pipelines-page__row--head)").first();
  await expect(row).toBeVisible();
  const state = (await row.locator(".pipelines-page__row-state").textContent()).trim();
  return { row, state };
}

test("a maintainer is sent away from the pipelines page", async ({ maintainerPage: page }) => {
  await page.goto(PAGE);

  await expect(page).not.toHaveURL(/\/pipelines/);
});

test("an admin must confirm before a scrape starts", async ({ adminPage: page }) => {
  const posted = await stubBatch(page, BATCH);

  await page.goto(PAGE);
  const { row, state } = await firstRow(page);

  await row.getByRole("button", { name: "Run now" }).click();
  expect(posted.body).toBeNull();

  await page.getByRole("button", { name: "Start", exact: true }).click();
  await expect.poll(() => posted.body).not.toBeNull();
  expect(posted.body.state).toBe(state);
});

test("a chosen pipeline's Run now starts that pipeline's pass", async ({ adminPage: page }) => {
  const posted = await stubBatch(page, LAW_BATCH);

  await page.goto(PAGE);
  await page.getByRole("button", { name: "Governing law" }).click();
  await expect(page.getByRole("button", { name: "Governing law" })).toHaveAttribute("aria-pressed", "true");
  const { row, state } = await firstRow(page);

  await row.getByRole("button", { name: "Run now" }).click();
  await page.getByRole("button", { name: "Start", exact: true }).click();

  await expect.poll(() => posted.body).not.toBeNull();
  expect(posted.body.state).toBe(state);
});
