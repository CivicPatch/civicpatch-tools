/**
 * User story: reviewer approves a card, or rejects it
 *
 * Given I am reviewing a card
 * When I click Approve
 * Then my edits are sent to the approve endpoint
 * And the card is credited as resolved and I move on to the next one
 * But if the approve is rejected I stay put, with the reason shown
 * And when I click Reject instead, the scrape is dismissed and I move on
 *
 * Approving writes the roster and commits to open-data, which the e2e stack has
 * no credentials for, so both requests are stubbed: this tests the client wiring
 * — that each button reaches the right endpoint with the right payload and
 * drives the right state — not the publish itself.
 */

import { test, expect } from "../fixtures/index.js";
import { editField } from "./helpers/review-card.js";

const APPROVE_ENDPOINT = "**/api/v1/reviews/*/publish";
// The id is a path segment, not a query parameter — `*` does not cross a slash, so this
// matches `/reviews/{id}` without also catching `/reviews/{id}/save`.
const REJECT_ENDPOINT = "**/api/v1/reviews/*";

const FIRST_CARD_REQUEST_ID = "00000000-0000-0000-eeee-000000000001";

async function openFirstCard(page) {
  await page.goto("/review");
  await page.locator(".review-page__start-btn").click();
  await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");
}

test.describe("Approve", () => {
  test("sends the card to the approve endpoint", async ({
    authenticatedPage: page,
  }) => {
    let approveBody = null;
    await page.route(APPROVE_ENDPOINT, async (route) => {
      approveBody = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "published" }),
      });
    });

    await openFirstCard(page);
    await page.locator(".review-page__approve-btn").click();

    await expect.poll(() => approveBody).not.toBeNull();
    expect(approveBody.request_id).toBe(FIRST_CARD_REQUEST_ID);
    expect(approveBody.jurisdiction_ocdid).toBeTruthy();
  });

  test("carries the reviewer's edits when the card is dirty", async ({
    authenticatedPage: page,
  }) => {
    let approveBody = null;
    await page.route(APPROVE_ENDPOINT, async (route) => {
      approveBody = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "published" }),
      });
    });

    await openFirstCard(page);

    // Any edit will do — this is about what approve sends, not the field. The seat is picked
    // from a select now, so there is no office text to type into.
    await editField(page, "Jane Smith", "Other names", "Janey Smith");

    // A dirty card approves under different wording — and must send the patch.
    const approveBtn = page.locator(".review-page__approve-btn");
    await expect(approveBtn).toHaveText(/Save and approve/);
    await approveBtn.click();

    await expect.poll(() => approveBody).not.toBeNull();
    expect(JSON.stringify(approveBody.data)).toContain("Janey Smith");
  });

  test("an approved card is credited as resolved and the reviewer moves on", async ({
    authenticatedPage: page,
  }) => {
    await page.route(APPROVE_ENDPOINT, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "published" }),
      }),
    );

    await openFirstCard(page);
    await page.locator(".review-page__approve-btn").click();

    await expect(page.locator(".review-page__progress")).toContainText("2");
    await expect(page.locator(".review-page__dot").nth(0)).toHaveClass(
      /review-page__dot--resolved/,
    );
  });

  test("a refused approve keeps the reviewer on the card and shows why", async ({
    authenticatedPage: page,
  }) => {
    await page.route(APPROVE_ENDPOINT, (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error: "Publish failed" }),
      }),
    );

    await openFirstCard(page);
    await page.locator(".review-page__approve-btn").click();

    await expect(page.locator(".review-page__progress")).toContainText("1");
    await expect(page.locator(".review-page__error")).toBeVisible();
  });
});

test.describe("Reject", () => {
  test("dismisses the scrape and moves the reviewer on", async ({
    authenticatedPage: page,
  }) => {
    let rejectUrl = null;
    await page.route(REJECT_ENDPOINT, async (route) => {
      if (route.request().method() !== "DELETE") return route.fallback();
      rejectUrl = route.request().url();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "success" }),
      });
    });

    await openFirstCard(page);
    await page.getByRole("button", { name: "Reject" }).click();

    await expect.poll(() => rejectUrl).not.toBeNull();
    expect(rejectUrl).toContain(`/reviews/${FIRST_CARD_REQUEST_ID}`);

    // Rejecting is a completed review action, so it advances like approving.
    await expect(page.locator(".review-page__progress")).toContainText("2");
  });
});
