/**
 * User story: a maintainer looks for where to intervene
 *
 * Given scrapes and imports have been running across states
 * When I open the changesets page, I see what is waiting on a reviewer per state
 * And I can open a state to see which localities are behind each figure
 * And I can start that state's scrape, after being asked to confirm
 *
 * The read path is NOT stubbed: the rollup, calendar and bucket endpoints answer from the
 * seeded database, so this catches the backend changing their shape.
 *
 * Starting a scrape is stubbed — it reaches Temporal, which the e2e stack has no credentials
 * for. So that half tests the client wiring only: that the button reaches
 * POST /pipeline_runs/batch with the right state, behind a confirm.
 *
 * Note what the stub does NOT cover: it is a hand-written copy of the endpoint's shape, so a
 * field removed server-side still breaks the page and still passes here.
 */

import { test, expect } from "../fixtures/index.js";

const PAGE = "/activity/changesets";
const BATCH = "**/api/v1/pipeline_runs/batch";

test("the page lists a row per state, and sorting reorders them", async ({
  authenticatedPage: page,
}) => {
  await page.goto(PAGE);

  const rows = page.locator(".cs-row");
  await expect(rows.first()).toBeVisible();
  const byQueue = await page.locator(".cs-row__state").allTextContents();

  await page.getByRole("button", { name: "State" }).click();
  const byName = await page.locator(".cs-row__state").allTextContents();

  // Sorted by name is the seeded states in alphabetical order, whatever they are.
  expect(byName).toEqual([...byName].sort());
  expect(byName.length).toBe(byQueue.length);
});

test("a calendar cell says what ran that day", async ({
  authenticatedPage: page,
}) => {
  await page.goto(PAGE);
  await expect(page.locator(".cs-row").first()).toBeVisible();

  // The popover is CSS-driven on hover, so its content is in the DOM either way — what matters
  // is that a day with runs names them rather than only colouring a band.
  const populated = page
    .locator(".cs-cal__cell:not(.cs-cal__cell--idle)")
    .first();
  await expect(populated).toHaveCount(1);
  await expect(populated.locator(".cs-pop__head")).toContainText("—");
});

test("opening a state loads the localities behind its figures", async ({
  authenticatedPage: page,
}) => {
  let bucketRequests = 0;
  page.on("request", (req) => {
    if (req.url().includes("/changeset_summaries/buckets/"))
      bucketRequests += 1;
  });

  await page.goto(PAGE);
  const section = page.locator(".cs-section").first();
  await expect(section).toBeVisible();

  // Counted as requests, not elements: a closed <details> still renders its body, so the list
  // is in the DOM either way. 15 states x 3 buckets eagerly would be 45 requests on load.
  expect(bucketRequests).toBe(0);

  await section.locator("summary").click();
  await expect(section.locator(".cs-bucket__head").first()).toBeVisible();
  expect(bucketRequests).toBeGreaterThan(0);
});

test("a contributor is not offered the scrape control", async ({
  authenticatedPage: page,
}) => {
  await page.goto(PAGE);
  await page.locator(".cs-section").first().locator("summary").click();

  await expect(page.locator(".cs-scrape__btn")).toHaveCount(0);
});

test("a maintainer must confirm before a scrape starts", async ({
  maintainerPage: page,
}) => {
  let posted = null;
  await page.route(BATCH, async (route) => {
    posted = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: { workflow_id: "state-scrape-e2e", state: posted.state },
      }),
    });
  });

  await page.goto(PAGE);
  await expect(page.locator(".cs-section").first()).toBeVisible();

  // Whichever state has no run of its own in flight. Picking the first section instead would
  // depend on how the seed happens to sort, and the seeded queue leaves one state busy.
  const startable = page.locator(".cs-section").filter({
    has: page.locator(".cs-scrape__btn:not([disabled])"),
  });
  const section = startable.first();
  await section.locator("summary").click();
  const state = (
    await section.locator(".cs-section__state").textContent()
  ).trim();

  await section.locator(".cs-scrape__btn").click();
  // Nothing fires on click: a batch spends real money and cannot be recalled.
  expect(posted).toBeNull();

  await page.getByRole("button", { name: /start scraping/i }).click();
  await expect.poll(() => posted).not.toBeNull();
  expect(posted.state).toBe(state);
});

test("a state already scraping cannot be started again", async ({
  maintainerPage: page,
}) => {
  // The UI half of the guard. The other half is the workflow id: `state-scrape-{state}` with
  // FAIL on conflict, so a second start is refused even if this button is bypassed.
  await page.goto(PAGE);
  await expect(page.locator(".cs-section").first()).toBeVisible();

  const busy = page.locator(".cs-section").filter({
    has: page.locator(".cs-scrape__btn[disabled]"),
  });
  if ((await busy.count()) === 0)
    test.skip(true, "no state has a run in flight");

  await busy.first().locator("summary").click();
  await expect(busy.first().locator(".cs-scrape__busy")).toContainText(
    "already running",
  );
});
