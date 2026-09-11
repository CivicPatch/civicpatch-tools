/**
 * User story: an admin rolls back a user's hand-made edits, from that user's history page
 *
 * Given I open a user's history page (/~{username}/history)
 * Then their currently-active claims load into a list, none pre-selected
 * When I select some and click "Roll back N selected"
 * Then a confirm step appears first — rollback has no built-in undo, so this is one-way
 * And only on confirming are exactly the selected ids sent to the rollback endpoint
 * But if there's nothing left to roll back, the failure is shown, not silently dropped
 *
 * The page itself does a real, unstubbable server-side username lookup (`/~{username}` resolves
 * against the DB, not the API), so it targets the seeded e2e test user rather than a fake one.
 * The user, candidates and rollback endpoints still touch real assertions/roster state the e2e
 * stack has no fixtures for, so those three stay stubbed (wildcarded on user id, since the
 * seeded user's id is DB-assigned, not fixed): this tests the client wiring — that the page
 * reaches the right endpoints with the right payloads and drives the right UI state — not the
 * rollback mechanics themselves (covered by the backend's own integration tests).
 */

import { test, expect } from "../fixtures/index.js";

const TARGET_USERNAME = "e2e-test-user";
const USER_ENDPOINT = "**/api/admin/users/*";
const CANDIDATES_ENDPOINT = "**/api/admin/users/*/rollback-candidates";
const ROLLBACK_ENDPOINT = "**/api/admin/users/*/rollback";

const TARGET_USER = {
  id: "10000000-0000-0000-0000-000000000001",
  email: "target@example.com",
  username: TARGET_USERNAME,
  provider: "supabase",
  role: "maintainers",
  last_login_at: null,
};

const CANDIDATES = [
  {
    assertion_id: "a1",
    entity_id: "person-1",
    entity_label: "Ada Chen",
    field_path: "name",
    value: "Ada M. Chen",
    jurisdiction_ocdid: "ocd-jurisdiction/country:us/state:nj/place:e2e/government",
    status: "active",
    created_at: "2026-09-01T12:00:00+00:00",
  },
  {
    assertion_id: "a2",
    entity_id: "person-1",
    entity_label: "Ada Chen",
    field_path: "phones",
    value: "555-0100",
    jurisdiction_ocdid: "ocd-jurisdiction/country:us/state:nj/place:e2e/government",
    status: "active",
    created_at: "2026-09-02T12:00:00+00:00",
  },
];

async function stubUser(page) {
  await page.route(USER_ENDPOINT, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: TARGET_USER }),
    }),
  );
}

async function stubCandidates(page, candidates = CANDIDATES) {
  await page.route(CANDIDATES_ENDPOINT, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: candidates }),
    }),
  );
}

async function openHistoryPage(page) {
  await page.goto(`/~${TARGET_USERNAME}/history`);
  await expect(page.locator(".candidate-row")).toHaveCount(CANDIDATES.length);
}

async function selectAll(page) {
  await page.locator(".candidate-row-list__select-all input[type=checkbox]").check();
}

test.describe("User history page rollback", () => {
  test("loads a user's candidates, unselected", async ({ adminPage: page }) => {
    await stubUser(page);
    await stubCandidates(page);

    await openHistoryPage(page);

    await expect(page.locator(".candidate-row input[type=checkbox]").nth(0)).not.toBeChecked();
    await expect(page.locator(".candidate-row input[type=checkbox]").nth(1)).not.toBeChecked();
    await expect(page.getByText("Select all (2)")).toBeVisible();
    await expect(page.getByRole("button", { name: "Roll back 0 selected" })).toBeDisabled();

    await selectAll(page);

    await expect(page.locator(".candidate-row input[type=checkbox]").nth(0)).toBeChecked();
    await expect(page.locator(".candidate-row input[type=checkbox]").nth(1)).toBeChecked();
    await expect(page.getByRole("button", { name: "Roll back 2 selected" })).toBeEnabled();
  });

  test("rolling back asks for confirmation before sending anything", async ({
    adminPage: page,
  }) => {
    await stubUser(page);
    await stubCandidates(page);
    let rollbackCalled = false;
    await page.route(ROLLBACK_ENDPOINT, async (route) => {
      rollbackCalled = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: { withdrawn: 2 } }),
      });
    });

    await openHistoryPage(page);
    await selectAll(page);
    await page.getByRole("button", { name: "Roll back 2 selected" }).click();

    // Not `.toBeVisible()` on the wrapper itself: `<dialog>` opened via `showModal()` renders
    // in the browser's top-layer, so a non-shadow-DOM custom element wrapping it reports a
    // zero-size bounding box even though the dialog is fully visible — assert on real content
    // inside it instead.
    await expect(page.getByRole("heading", { name: "Are you sure?" })).toBeVisible();
    expect(rollbackCalled).toBe(false);

    // Cancel — still nothing sent.
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.locator("confirm-rollback-modal")).toHaveCount(0);
    expect(rollbackCalled).toBe(false);
  });

  test("confirming sends exactly the selected assertion ids", async ({ adminPage: page }) => {
    await stubUser(page);
    await stubCandidates(page);
    let rollbackBody = null;
    await page.route(ROLLBACK_ENDPOINT, async (route) => {
      rollbackBody = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: { withdrawn: 1 } }),
      });
    });

    await openHistoryPage(page);
    // Check only the first candidate — only it should be sent.
    await page.locator(".candidate-row input[type=checkbox]").nth(0).check();
    await page.getByRole("button", { name: "Roll back 1 selected" }).click();
    await page
      .locator("confirm-rollback-modal")
      .getByRole("button", { name: "Roll back" })
      .click();

    await expect.poll(() => rollbackBody).not.toBeNull();
    expect(rollbackBody.assertion_ids).toEqual(["a1"]);

    await expect(page.locator("confirm-rollback-modal")).toHaveCount(0);
    await expect(page.locator(".status-toast")).toContainText("Rolled back 1 change");
  });

  test("a failed rollback surfaces the error instead of closing silently", async ({
    adminPage: page,
  }) => {
    await stubUser(page);
    await stubCandidates(page);
    await page.route(ROLLBACK_ENDPOINT, (route) =>
      route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Nothing to roll back" }),
      }),
    );

    await openHistoryPage(page);
    await selectAll(page);
    await page.getByRole("button", { name: "Roll back 2 selected" }).click();
    await page
      .locator("confirm-rollback-modal")
      .getByRole("button", { name: "Roll back" })
      .click();

    await expect(page.locator(".status-toast")).toContainText("Rollback failed");
  });
});
