/**
 * User story: the scrape read an organization's page and found nobody on it
 *
 * Given Eve sits on the parks board, and this scrape read the parks board page but listed nobody
 * When I open the card
 * Then the parks board keeps its section, says nothing was found there, and shows Eve leaving it
 */

import { test, expect } from "../fixtures/index.js";
import { SHAPES_CHANGESET_ID, SHAPES_PARKS_BOARD } from "../fixtures/db.js";

test("an organization read but found empty keeps its section and says so", async ({
  authenticatedPage: page,
}) => {
  await page.goto(`/review/session?changeset_id=${SHAPES_CHANGESET_ID}`);
  const parks = page.locator("review-overview .review-overview__organization", { hasText: SHAPES_PARKS_BOARD });
  await expect(parks.locator(".panel__cap")).toContainText("not found in this scrape, nothing here changes");
  await expect(parks).toContainText("Eve Parks");
});
