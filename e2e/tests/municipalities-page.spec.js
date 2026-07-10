/**
 * User story: browsing the full municipality list for a state — search, filter,
 * sort, and having that view state survive a reload via the URL.
 *
 * Client-side filter/sort/pagination/URL-param logic is unit-tested directly
 * (tests/municipalities-filter.test.ts, tests/municipalities-url-params.test.ts,
 * tests/municipalities-pagination.test.ts) — this spec verifies the real wiring:
 * the page loads with a live fetch, view state round-trips through the URL and
 * survives a reload (mirroring review-deep-link-stale.spec.js's URL-state
 * pattern), and controls actually mutate what's rendered in the table.
 *
 * Uses the shared NJ fixtures seeded by db.js (E2E Test City / City 2 / City 3 —
 * no `url`, no people, so all three classify as UNTRACKED) rather than
 * MAP_FIXTURES, whose jurisdiction row never gets a `scraped_at`, so its
 * "fresh"/"stale" names don't actually classify as fresh/stale.
 */

import { test, expect } from "../fixtures/index.js";

test.describe("Municipalities page", () => {
  test.beforeEach(async ({ page }) => {
    const responsePromise = page.waitForResponse(/\/api\/v1\/coverage\/nj\/municipalities/);
    await page.goto("/nj/local");
    const res = await responsePromise;
    expect(res.status()).toBe(200);
  });

  test("renders the seeded municipality list", async ({ page }) => {
    await expect(page.locator(".municipalities-table__row", { hasText: "E2E Test City 2" })).toBeVisible();
    await expect(page.locator(".municipalities-table__row", { hasText: "E2E Test City 3" })).toBeVisible();
  });

  test("search filters the table, updates the URL, and survives a reload", async ({ page }) => {
    await page.locator(".municipalities-controls__search").fill("City 2");

    const rows = page.locator(".municipalities-table__row");
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText("E2E Test City 2");
    await expect(page).toHaveURL(/[?&]q=City(\+|%20)2(&|$)/);

    await page.reload();
    await expect(page.locator(".municipalities-controls__search")).toHaveValue("City 2");
    await expect(page.locator(".municipalities-table__row")).toHaveCount(1);
  });

  test("status pill filters to an empty state, and Clear filters resets it", async ({ page }) => {
    await page.locator(".municipalities-controls__pill", { hasText: "Fresh" }).click();

    await expect(page.locator(".municipalities-table__empty")).toBeVisible();
    await expect(page).toHaveURL(/[?&]status=fresh(&|$)/);

    await page.locator(".municipalities-table__empty button", { hasText: "Clear filters" }).click();

    await expect(page.locator(".municipalities-table__empty")).toHaveCount(0);
    await expect(page).toHaveURL(/\/nj\/local$/);
  });

  test("sort toggles row order and updates the URL", async ({ page }) => {
    await page.locator(".municipalities-controls__search").fill("City");

    const nameCells = page.locator(".municipalities-table__row td:first-child");
    await expect(nameCells).toHaveCount(3);
    await expect(nameCells.first()).toContainText("E2E Test City");
    await expect(nameCells.last()).toContainText("E2E Test City 3");

    await page.locator(".municipalities-table__sort-btn", { hasText: "Municipality" }).click();

    await expect(nameCells.first()).toContainText("E2E Test City 3");
    await expect(page).toHaveURL(/[?&]dir=desc(&|$)/);
  });
});
