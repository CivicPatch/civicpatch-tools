/**
 * User story: reviewer reports a data problem they can't fix from the card
 *
 * Given I am reviewing a card and spot something wrong
 * When I open "Report issue", describe it, and file it
 * Then the description is sent for that card
 * And the filed issue is listed on the card
 * But if filing fails the modal stays open and tells me
 * And issues already filed against a card are listed when it loads
 *
 * Filing creates a real GitHub issue, which the e2e stack has no credentials
 * for, so both verbs on the issues endpoint are stubbed. This tests the client
 * wiring — that the button, modal and list are connected to the right request
 * for the card under review.
 */

import { test, expect } from "../fixtures/index.js";

const ISSUES_ENDPOINT = "**/api/v1/reviews/*/issues";
const FIRST_CARD_REQUEST_ID = "00000000-0000-0000-eeee-000000000001";

function filedIssue(number) {
  return {
    id: `issue-${number}`,
    github_issue_url: `https://github.com/civicpatch/open-data/issues/${number}`,
    github_issue_number: number,
    status: "pending",
  };
}

// Serves an empty list on GET; POST is left to each test.
async function stubNoExistingIssues(page) {
  await page.route(ISSUES_ENDPOINT, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: [] }),
    });
  });
}

async function openFirstCard(page) {
  await page.goto("/review");
  await page.locator(".review-page__start-btn").click();
  await expect(page.locator(".review-page__jurisdiction")).toHaveText("E2E Test City");
}

test.describe("Report issue", () => {
  test("files the description against the card under review", async ({
    authenticatedPage: page,
  }) => {
    let postUrl = null;
    let postBody = null;
    await page.route(ISSUES_ENDPOINT, async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      postUrl = route.request().url();
      postBody = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: filedIssue(42) }),
      });
    });
    await stubNoExistingIssues(page);

    await openFirstCard(page);
    await page.getByRole("button", { name: "Report issue" }).click();

    await page
      .locator(".report-issue-modal__textarea")
      .fill("Council member listed twice");
    await page.getByRole("button", { name: "File issue" }).click();

    await expect.poll(() => postBody).not.toBeNull();
    expect(postBody.description).toBe("Council member listed twice");
    // The issue must be filed against the card being reviewed, not another one.
    expect(postUrl).toContain(FIRST_CARD_REQUEST_ID);
  });

  test("a filed issue closes the modal and is listed on the card", async ({
    authenticatedPage: page,
  }) => {
    await page.route(ISSUES_ENDPOINT, async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: filedIssue(42) }),
      });
    });
    await stubNoExistingIssues(page);

    await openFirstCard(page);
    await page.getByRole("button", { name: "Report issue" }).click();
    await page.locator(".report-issue-modal__textarea").fill("Wrong term dates");
    await page.getByRole("button", { name: "File issue" }).click();

    await expect(page.locator(".report-issue-modal__textarea")).toHaveCount(0);

    const reported = page.locator(".review-page__reported-issues");
    await expect(reported).toContainText("Issue #42");
    await expect(reported.locator("a")).toHaveAttribute(
      "href",
      "https://github.com/civicpatch/open-data/issues/42",
    );
  });

  test("a failed filing keeps the modal open and reports the failure", async ({
    authenticatedPage: page,
  }) => {
    await page.route(ISSUES_ENDPOINT, async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error: "GitHub rejected the issue" }),
      });
    });
    await stubNoExistingIssues(page);

    await openFirstCard(page);
    await page.getByRole("button", { name: "Report issue" }).click();
    await page.locator(".report-issue-modal__textarea").fill("Missing email");
    await page.getByRole("button", { name: "File issue" }).click();

    // Modal stays up so the description isn't lost, with the reason shown.
    await expect(page.locator(".report-issue-modal__textarea")).toBeVisible();
    await expect(
      page.locator(".report-issue-modal__form .review-page__error"),
    ).toContainText("Failed to file issue");
  });

  test("issues already filed against a card are listed when it loads", async ({
    authenticatedPage: page,
  }) => {
    await page.route(ISSUES_ENDPOINT, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [filedIssue(7)] }),
      });
    });

    await openFirstCard(page);

    await expect(page.locator(".review-page__reported-issues")).toContainText(
      "Issue #7",
    );
  });
});
