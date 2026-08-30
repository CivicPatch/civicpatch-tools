/**
 * User story: a maintainer imports a curated sheet
 *
 * Given the roster sheet has rows
 * When I import, I am told what was read and what was rejected
 * And the page follows the run to completion on its own
 * Then I review what it produced and publish the localities I pick
 *
 * Everything the importer does crosses into Google Sheets, which the e2e stack has no
 * credentials for, so the endpoints are stubbed: this tests the client wiring — that each
 * button reaches the right endpoint and the page moves through import → progress → review →
 * publish — not the import itself. A finished import switches to the History tab on its own,
 * which is where the review panel lives.
 *
 * Note what that does NOT cover: the stubs are a hand-written copy of the API's shape, so they
 * cannot catch the backend changing it. A field removed server-side still breaks the page and
 * still passes here. Only a seeded batch answered by the real endpoints would catch that.
 */

import { test, expect } from "../fixtures/index.js";

const SHEET = "**/api/internal/imports/sheet";
const LATEST = "**/api/internal/imports/latest";
const START = "**/api/internal/imports";
const PROGRESS = "**/api/internal/imports/batch-e2e";
const REVIEW = "**/api/internal/imports/batch-e2e/review";
const PUBLISH = "**/api/internal/imports/batch-e2e/publish";

const READY = "ocd-jurisdiction/country:us/state:wa/place:e2e_ready/government";
const BLOCKED = "ocd-jurisdiction/country:us/state:wa/place:e2e_blocked/government";

const PREVIEW_BODY = {
  jurisdictions_ready: [READY],
  jurisdictions_blocked: [BLOCKED],
  rows: 3,
  errors: [
    {
      line: 4,
      jurisdiction_ocdid: BLOCKED,
      column: "label",
      message: "required",
    },
  ],
};

const person = (overrides = {}) => ({
  id: "00000000-0000-0000-cccc-000000000001",
  name: "Ada Whitfield",
  label: "Council Member",
  image: null,
  urls: [],
  phones: [],
  emails: [],
  start_date: null,
  end_date: null,
  role_id: "council-member",
  unmatched_text: [],
  ...overrides,
});

const progress = (status, done = 1) => ({
  batch_id: "batch-e2e",
  status,
  items_total: 1,
  items_done: done,
  error: null,
  started_at: "2026-08-28T14:02:00Z",
  finished_at: status === "running" ? null : "2026-08-28T14:02:05Z",
});

const reviewBody = (people) => ({
  batch_id: "batch-e2e",
  status: "succeeded",
  jurisdictions: [
    {
      jurisdiction_ocdid: READY,
      name: "E2E Ready",
      request_id: "00000000-0000-0000-dddd-000000000001",
      review_status: "pending",
      people,
    },
  ],
});

async function json(route, body) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ data: body }),
  });
}

/** Every route the page touches on load, so nothing reaches Google. */
async function stubIdle(page) {
  await page.route(SHEET, (route) =>
    json(route, { url: "https://docs.google.com/spreadsheets/d/e2e" }),
  );
  await page.route(LATEST, (route) => json(route, null));
}

test.describe("Import from the sheet", () => {
  test("importing reports what was read and what was rejected", async ({
    maintainerPage: page,
  }) => {
    await stubIdle(page);
    await page.route(PROGRESS, (route) => json(route, progress("succeeded")));
    await page.route(REVIEW, (route) => json(route, reviewBody([person()])));
    await page.route(START, (route) =>
      route.request().method() === "POST"
        ? json(route, { batch_id: "batch-e2e", preview: PREVIEW_BODY })
        : route.fallback(),
    );

    await page.goto("/imports");
    await page.getByRole("button", { name: "Import", exact: true }).click();

    const summary = page.locator(".import-summary");
    await expect(
      summary.getByRole("row").filter({ hasText: "rows found" }),
    ).toContainText("3");
    await expect(
      summary.getByRole("row").filter({ hasText: "jurisdictions found" }),
    ).toContainText("1");

    // The rejected row names its line, column and locality, so it is fixable in the sheet.
    await expect(page.getByRole("cell", { name: "4", exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: "label" })).toBeVisible();
    await expect(page.getByText(BLOCKED)).toBeVisible();
  });

  test("links to the sheet being read", async ({ maintainerPage: page }) => {
    await stubIdle(page);
    await page.goto("/imports");

    await expect(page.getByRole("link", { name: "Open the sheet" })).toHaveAttribute(
      "href",
      "https://docs.google.com/spreadsheets/d/e2e",
    );
  });

  test("follows a started import through to its review without a reload", async ({
    maintainerPage: page,
  }) => {
    await stubIdle(page);
    await page.route(REVIEW, (route) => json(route, reviewBody([person()])));

    // Running on the first poll, finished on the next: the page has to keep asking.
    let polls = 0;
    await page.route(PROGRESS, (route) =>
      json(route, progress(polls++ === 0 ? "running" : "succeeded")),
    );
    await page.route(START, (route) =>
      route.request().method() === "POST"
        ? json(route, { batch_id: "batch-e2e", preview: PREVIEW_BODY })
        : route.fallback(),
    );

    await page.goto("/imports");
    await page.getByRole("button", { name: "Import", exact: true }).click();

    await expect(page.getByText("Importing…")).toBeVisible();
    // Arrives on its own — the poll used to die before the first batch existed, leaving this
    // stuck until somebody reloaded.
    await expect(page.getByText("Review and publish")).toBeVisible();
    await expect(page.getByText("Ada Whitfield")).toBeVisible();
  });

  test("warns about a label that matched no role", async ({
    maintainerPage: page,
  }) => {
    await stubIdle(page);
    await page.route(LATEST, (route) => json(route, progress("succeeded")));
    await page.route(PROGRESS, (route) => json(route, progress("succeeded")));
    await page.route(REVIEW, (route) =>
      json(
        route,
        reviewBody([
          person({ role_id: null, unmatched_text: ["Grand Poobah"] }),
        ]),
      ),
    );

    await page.goto("/imports");

    await expect(page.locator(".review-unmatched")).toContainText("Grand Poobah");
  });

  test("publishes only the localities that were picked", async ({
    maintainerPage: page,
  }) => {
    await stubIdle(page);
    await page.route(LATEST, (route) => json(route, progress("succeeded")));
    await page.route(PROGRESS, (route) => json(route, progress("succeeded")));
    await page.route(REVIEW, (route) => json(route, reviewBody([person()])));

    let published = null;
    await page.route(PUBLISH, async (route) => {
      published = route.request().postDataJSON();
      await json(route, [{ jurisdiction_ocdid: READY, published: true, error: null }]);
    });

    await page.goto("/imports");
    await expect(page.getByText("Review and publish")).toBeVisible();

    await page.getByRole("checkbox", { name: "Select all" }).check();
    // Echoed above and below the localities; either one publishes the same selection.
    await page.getByRole("button", { name: "Publish" }).first().click();

    await expect.poll(() => published).not.toBeNull();
    expect(published.jurisdiction_ocdids).toEqual([READY]);
    await expect(page.getByText("in one open-data commit")).toBeVisible();
  });
});
