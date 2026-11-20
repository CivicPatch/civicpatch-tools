/**
 * User story: someone the scrape dropped from one of their two organizations
 *
 * Given Ada sits on the council and the school board, and this scrape lists her on the council only
 * When I open the card
 * Then her school board row reads as leaving, and her council row does not
 * And restoring that row keeps both her seats in what Approve sends
 *
 * The roster edit goes to the real endpoint, so it proves the restored post exists; publish is stubbed.
 */

import { test, expect } from "../fixtures/index.js";
import { SHAPES_CHANGESET_ID } from "../fixtures/db.js";
import { openEditorFor, rowFor } from "./helpers/review-card.js";

const PUBLISH_ENDPOINT = "**/api/v1/reviews/*/publish";

test("a row the scrape dropped reads as leaving that organization only", async ({
  authenticatedPage: page,
}) => {
  await page.goto(`/review/session?changeset_id=${SHAPES_CHANGESET_ID}`);

  const leaving = rowFor(page, "Ada Both");
  await expect(leaving).toHaveCount(1);
  await expect(leaving.locator(".review-row__badge")).toHaveText("Not in scrape");
  // Ada's school board row and Eve, whose parks board page listed nobody.
  await expect(page.locator(".review-overview__tally")).toContainText("2 not in scrape");
});

test("restoring that row keeps both seats in the published payload", async ({
  authenticatedPage: page,
}) => {
  let payload = null;
  await page.route(PUBLISH_ENDPOINT, async (route) => {
    payload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "success" }),
    });
  });

  await page.goto(`/review/session?changeset_id=${SHAPES_CHANGESET_ID}`);
  await openEditorFor(page, "Ada Both");
  await page.locator(".person-editor__restore-person").click();
  await expect(rowFor(page, "Ada Both").locator(".review-row__badge")).toHaveText("Restored");

  const rosterEdit = page.waitForResponse(
    (response) => response.url().endsWith("/roster-edits") && response.request().method() === "POST",
  );
  await page.locator(".review-session__approve-btn").click();
  const response = await rosterEdit;
  expect(response.status()).toBe(200);
  const people = response.request().postDataJSON().people;
  const withOffices = people.filter((person) => person.offices);
  expect(withOffices).toHaveLength(1);
  expect(withOffices[0].offices).toHaveLength(2);
  await expect.poll(() => payload).not.toBeNull();
});
