/**
 * User story: visitor browses the map and selects a state
 *
 * Given the seeded NJ map fixtures
 * When I land on the home page
 * Then the map renders
 * And selecting NJ fetches local status and shows the reset button
 * And clicking reset clears the state selector and hides the reset button
 * And the national view actually renders the coverage fill layer
 *
 * The paint expressions themselves are unit-tested (applyLocalStatus, etc.),
 * but a map-load-timing regression once silently stopped the layers from being
 * added at all — invisible to DOM-only checks — so the render assertion below
 * verifies the layer/source/feature-state pipeline end-to-end.
 */

import { test, expect } from "../fixtures/index.js";

test.describe("Browse map", () => {
  test.beforeEach(async ({ page }) => {
    // The pmtiles bucket allowlists origins for CORS — it answers `https://civicpatch.org` and
    // nobody else, so from localhost the browser blocks every range fetch and the states layer
    // silently has no features. Proxy through Node, which has no CORS, and return the bytes with
    // the header the browser wants. Not a stub: the tiles are the real ones, so a change to them
    // still shows up here.
    await page.route("https://cdn.civicpatch.org/maps/**", async (route) => {
      const response = await route.fetch();
      await route.fulfill({
        response,
        headers: {
          ...response.headers(),
          "access-control-allow-origin": "*",
          "access-control-expose-headers": "content-range,content-length,etag",
        },
      });
    });
    // Wipe persisted default-state so each test starts at the national view.
    await page.addInitScript(() => localStorage.clear());
    await page.goto("/");
  });

  test("home page renders the map and state selector", async ({ page }) => {
    await expect(page.locator(".map-container")).toBeVisible();
    await expect(page.locator("civ-select-state select")).toBeVisible();
    await expect(page.locator(".map-reset-btn")).toHaveCount(0);
  });

  test("selecting a state fetches local status and reveals the reset button", async ({ page }) => {
    const responsePromise = page.waitForResponse(/\/api\/v1\/coverage\/nj\/local/);
    await page.locator("civ-select-state select").selectOption("nj");
    const res = await responsePromise;
    expect(res.status()).toBe(200);

    await expect(page.locator(".map-reset-btn")).toBeVisible();
    await expect(page.locator("civ-select-state select")).toHaveValue("nj");
  });

  test("national view adds the states fill layer and applies coverage feature-state", async ({ page }) => {
    // `isSourceLoaded` goes true when the source is *registered*, before any tile for the
    // current viewport has been parsed — so wait for the features themselves.
    await page.waitForFunction(() => {
      const map = document.querySelector(".map-inner")?._map;
      if (!map || !map.getLayer("states") || !map.isSourceLoaded("national")) return false;
      return map.querySourceFeatures("national", { sourceLayer: "states" }).length > 0;
    }, null, { timeout: 30000 });

    const result = await page.evaluate(() => {
      const map = document.querySelector(".map-inner")._map;
      const feats = map.querySourceFeatures("national", { sourceLayer: "states" });
      const withCoverage = feats.filter(
        (f) => map.getFeatureState({ source: "national", sourceLayer: "states", id: f.id }).coverage !== undefined,
      );
      return {
        statesVisible: map.getLayoutProperty("states", "visibility"),
        featureCount: feats.length,
        withCoverageCount: withCoverage.length,
      };
    });

    expect(result.statesVisible).toBe("visible");
    expect(result.featureCount).toBeGreaterThan(0);
    expect(result.withCoverageCount).toBeGreaterThan(0);
  });

  test("reset clears the state selector and hides itself", async ({ page }) => {
    // The button appears when the drill level leaves `national`, which the state effect only
    // does once the style is ready — so wait for the fetch that selection kicks off, as the
    // sibling test above does. Asserting straight after `selectOption` races the map's load.
    const selected = page.waitForResponse(/\/api\/v1\/coverage\/nj\/local/);
    await page.locator("civ-select-state select").selectOption("nj");
    await selected;
    await expect(page.locator(".map-reset-btn")).toBeVisible();

    await page.locator(".map-reset-btn").click();

    await expect(page.locator("civ-select-state select")).toHaveValue("");
    await expect(page.locator(".map-reset-btn")).toHaveCount(0);
  });
});
