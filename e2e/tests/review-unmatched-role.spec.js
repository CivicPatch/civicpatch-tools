/**
 * User story: a scraped role the jurisdiction's role list does not know
 *
 * Given the scrape lists Finn as "Dogcatcher"
 * When I open the card
 * Then his post reads "none yet", never the placeholder role id, and his own label still shows
 */

import { test, expect } from "../fixtures/index.js";
import { SHAPES_CHANGESET_ID } from "../fixtures/db.js";
import { rowFor } from "./helpers/review-card.js";

test("an unmatched role names no post", async ({ authenticatedPage: page }) => {
  await page.goto(`/review/session?changeset_id=${SHAPES_CHANGESET_ID}`);
  const finn = rowFor(page, "Finn Unknown");
  await expect(finn.locator(".pv--post")).toContainText("none yet");
  await expect(finn).not.toContainText("unmatched");
  await expect(finn).toContainText("Dogcatcher");
});
