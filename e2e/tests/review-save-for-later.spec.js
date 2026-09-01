/**
 * User story: reviewer commits edits without publishing
 *
 * Given I have edited a card but am not ready to publish it
 * When I click "Save updates"
 * Then my edits are sent to the save endpoint
 * And the card is marked saved and I move on to the next one
 * But if the save is rejected I stay put, with the card flagged and the reason shown
 *
 * The save endpoint writes the reviewer's patch to the job branch on GitHub
 * (_commit_people_patch → update_pull_request_file), which the e2e stack has no
 * credentials for. The request is stubbed so this stays a test of the client
 * wiring — that the button reaches the right endpoint with the reviewer's edits,
 * and that each outcome drives the right state — not of the GitHub write.
 */

import { test, expect } from "../fixtures/index.js";
import { editField } from "./helpers/review-card.js";

const SAVE_ENDPOINT = "**/api/v1/reviews/*/save";

// The first NJ card is the only seeded card carrying people, so it is the only
// one that can be made dirty.
async function openFirstCardAndEdit(page) {
  await page.goto("/review");
  await page.locator(".review-page__start-btn").click();
  await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");

  // Save only appears once there is something to save.
  await expect(page.locator(".review-page__save-btn")).toHaveCount(0);

  await editField(page, "Jane Smith", "Office", "Deputy Mayor");

  await expect(page.locator(".review-page__save-btn")).toBeVisible();
}

test.describe("Save updates", () => {
  test("sends the reviewer's edits to the save endpoint", async ({
    authenticatedPage: page,
  }) => {
    let savedBody = null;
    await page.route(SAVE_ENDPOINT, async (route) => {
      savedBody = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "saved" }),
      });
    });

    await openFirstCardAndEdit(page);
    await page.locator(".review-page__save-btn").click();

    await expect.poll(() => savedBody).not.toBeNull();
    expect(savedBody.request_id).toBe("00000000-0000-0000-eeee-000000000001");
    // The edit must actually reach the server — this is the payload the button wires up.
    expect(JSON.stringify(savedBody.data)).toContain("Deputy Mayor");
  });

  test("a saved card is marked saved and the reviewer moves on", async ({
    authenticatedPage: page,
  }) => {
    await page.route(SAVE_ENDPOINT, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "saved" }),
      }),
    );

    await openFirstCardAndEdit(page);
    await page.locator(".review-page__save-btn").click();

    // Saving advances, same as publishing does.
    await expect(page.locator(".review-page__progress")).toContainText("2");
    await expect(page.locator(".review-page__dot").nth(0)).toHaveClass(
      /review-page__dot--saved/,
    );
  });

  test("a rejected save keeps the reviewer on the card and shows why", async ({
    authenticatedPage: page,
  }) => {
    await page.route(SAVE_ENDPOINT, (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error: "Failed to update pull request data on GitHub" }),
      }),
    );

    await openFirstCardAndEdit(page);
    await page.locator(".review-page__save-btn").click();

    // Stay put so the reviewer can fix and retry.
    await expect(page.locator(".review-page__progress")).toContainText("1");
    await expect(page.locator(".review-page__error")).toBeVisible();

    // The dot only reads as failed from elsewhere — while you are on the card,
    // "current" takes precedence over "failed" in the status ladder.
    await page.locator(".review-page__next-btn").click();
    await expect(page.locator(".review-page__progress")).toContainText("2");
    await expect(page.locator(".review-page__dot").nth(0)).toHaveClass(
      /review-page__dot--failed/,
    );
  });
});
