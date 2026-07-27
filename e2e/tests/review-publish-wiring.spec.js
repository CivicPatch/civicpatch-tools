/**
 * User story: reviewer publishes a card, or closes its pull request
 *
 * Given I am reviewing a card
 * When I click Publish
 * Then my edits are sent to the save-and-merge endpoint
 * And the card is credited as resolved and I move on to the next one
 * But if the publish is rejected I stay put, with the reason shown
 * And when I click Close PR instead, the pull request is closed and I move on
 *
 * Publishing enqueues a real merge (GitHub + Temporal) and closing calls the
 * GitHub API, neither of which the e2e stack has credentials for. Both requests
 * are stubbed so this tests the client wiring — that each button reaches the
 * right endpoint with the right payload and drives the right state — rather than
 * the merge itself. The background merge poll is stubbed too, so it settles
 * instead of retrying for four minutes.
 */

import { test, expect } from "../fixtures/index.js";

const MERGE_ENDPOINT = "**/api/v1/pull_requests/*/save-and-merge";
const MERGE_STATUS_ENDPOINT = "**/api/v1/pull_requests/*/merge-status";
const CLOSE_ENDPOINT = "**/api/v1/pull_requests/*\\?request_id=*";

const FIRST_CARD_REQUEST_ID = "00000000-0000-0000-eeee-000000000001";

async function stubMergeSettles(page) {
  await page.route(MERGE_STATUS_ENDPOINT, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "merged" }),
    }),
  );
}

async function openFirstCard(page) {
  await page.goto("/review");
  await page.locator(".review-page__start-btn").click();
  await expect(page.getByText("E2E Test City")).toBeVisible();
}

test.describe("Publish", () => {
  test("sends the card to the save-and-merge endpoint", async ({
    authenticatedPage: page,
  }) => {
    let mergeBody = null;
    await stubMergeSettles(page);
    await page.route(MERGE_ENDPOINT, async (route) => {
      mergeBody = route.request().postDataJSON();
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ status: "enqueued" }),
      });
    });

    await openFirstCard(page);
    await page.locator(".review-page__merge-btn").click();

    await expect.poll(() => mergeBody).not.toBeNull();
    expect(mergeBody.request_id).toBe(FIRST_CARD_REQUEST_ID);
    expect(mergeBody.jurisdiction_ocdid).toBeTruthy();
  });

  test("carries the reviewer's edits when the card is dirty", async ({
    authenticatedPage: page,
  }) => {
    let mergeBody = null;
    await stubMergeSettles(page);
    await page.route(MERGE_ENDPOINT, async (route) => {
      mergeBody = route.request().postDataJSON();
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ status: "enqueued" }),
      });
    });

    await openFirstCard(page);

    const janeRow = page.locator(".people-diff__person").filter({ hasText: "Jane Smith" });
    await janeRow
      .locator(".people-diff__field")
      .filter({ hasText: "Office" })
      .first()
      .locator("input")
      .fill("Deputy Mayor");

    // A dirty card publishes under a different label — and must send the patch.
    const publishBtn = page.locator(".review-page__merge-btn");
    await expect(publishBtn).toHaveText(/Save and Publish/);
    await publishBtn.click();

    await expect.poll(() => mergeBody).not.toBeNull();
    expect(JSON.stringify(mergeBody.data)).toContain("Deputy Mayor");
  });

  test("a published card is credited as resolved and the reviewer moves on", async ({
    authenticatedPage: page,
  }) => {
    await stubMergeSettles(page);
    await page.route(MERGE_ENDPOINT, (route) =>
      route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ status: "enqueued" }),
      }),
    );

    await openFirstCard(page);
    await page.locator(".review-page__merge-btn").click();

    await expect(page.locator(".review-page__progress")).toContainText("2");
    await expect(page.locator(".review-page__dot").nth(0)).toHaveClass(
      /review-page__dot--resolved/,
    );
  });

  test("a rejected publish keeps the reviewer on the card and shows why", async ({
    authenticatedPage: page,
  }) => {
    await stubMergeSettles(page);
    await page.route(MERGE_ENDPOINT, (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error: "Merge could not be enqueued" }),
      }),
    );

    await openFirstCard(page);
    await page.locator(".review-page__merge-btn").click();

    await expect(page.locator(".review-page__progress")).toContainText("1");
    await expect(page.locator(".review-page__error")).toBeVisible();
  });
});

test.describe("Close PR", () => {
  test("closes the pull request and moves the reviewer on", async ({
    authenticatedPage: page,
  }) => {
    let closeUrl = null;
    await page.route(CLOSE_ENDPOINT, async (route) => {
      if (route.request().method() !== "DELETE") return route.fallback();
      closeUrl = route.request().url();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "success" }),
      });
    });

    await openFirstCard(page);
    await page.getByRole("button", { name: "Close PR" }).click();

    await expect.poll(() => closeUrl).not.toBeNull();
    expect(closeUrl).toContain(`request_id=${FIRST_CARD_REQUEST_ID}`);

    // Closing is a completed review action, so it advances like publishing.
    await expect(page.locator(".review-page__progress")).toContainText("2");
  });
});
