/**
 * User story: a maintainer looks for where to intervene
 *
 * Given scrapes and imports have been running across states
 * When I open the changesets page, I see what is waiting on a reviewer per state
 * And a calendar cell says what ran that day
 *
 * The read path is NOT stubbed: the rollup and calendar endpoints answer from the seeded
 * database, so this catches the backend changing their shape.
 *
 * This spec also covered per-state sections (their locality buckets) and starting a state's
 * scrape. The redesign (619b609f3, c43325999) removed the sections and moved the scrape
 * trigger to the pipelines page, admins only; those tests went with the sections, and the
 * scrape ones now live in `pipelines-scrape.spec.js`.
 */

import { test, expect } from "../fixtures/index.js";

const PAGE = "/activity/calendar";

test("the page lists a row per state, and sorting reorders them", async ({
  authenticatedPage: page,
}) => {
  await page.goto(PAGE);

  const rows = page.locator(".cs-row");
  await expect(rows.first()).toBeVisible();
  // The state rows only: the elections panel below reuses `.cs-row` for its own list. This
  // read every `.cs-row__state` until the elections section arrived and made the list unsorted.
  const states = page.locator(".secbody > div > .cs-row > .cs-row__state");
  const byQueue = await states.allTextContents();

  await page.getByRole("button", { name: "State" }).click();
  const byName = await states.allTextContents();

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
