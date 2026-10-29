/**
 * User story: a maintainer reads a roster comparison an agent made
 *
 * Given a saved run over the test jurisdiction (seeded by fixtures/db.js)
 * Then the page shows the people bar, the field rates and the jurisdictions
 * And a jurisdiction opens into its people, with their warnings
 * And a field's one-side-has-more count lists the people behind it, values tinted by side
 * And an outcome's count in the people bar lists those people across the state
 * And unticking an organization moves its civicpatch-only people out of the counts
 * And the state's jurisdictions not in the uploaded data open into a list
 * And a row's uploaded values open on keyboard focus, not only on hover
 *
 * Nothing is stubbed: the seeded run is answered by the real endpoints, so a change to the
 * API's shape fails here. What this does NOT cover is the comparison itself (the unit tests in
 * civicpatch.org/tests/unit/core do), since the run is seeded already computed.
 */

import { test, expect } from "../fixtures/index.js";
import { ROSTER_COMPARISON_RUN_ID } from "../fixtures/db.js";

const PAGE = `/roster-comparisons/${ROSTER_COMPARISON_RUN_ID}`;

test.describe("Roster comparison page", () => {
  test("shows the people bar, the field rates and the jurisdictions", async ({ maintainerPage: page }) => {
    await page.goto(PAGE);

    await expect(page.locator(".rc-legend")).toContainText("Matched 1");
    await expect(page.locator(".rc-legend")).toContainText("Only in civicpatch 1");
    await expect(page.getByRole("row").filter({ hasText: "Emails" })).toContainText("from Work Email");
    await expect(page.locator(".rc-jurisdiction")).toHaveCount(1);
    await expect(page.getByText("2 names reordered from 'Last, First'")).toBeVisible();
  });

  test("a jurisdiction opens into its people and their warnings", async ({ maintainerPage: page }) => {
    await page.goto(PAGE);
    await page.locator(".rc-jurisdiction").click();

    const detail = page.locator(".rc-jurisdiction-detail");
    await expect(detail.getByRole("row").filter({ hasText: "Pat Lin" })).toContainText("Only in uploaded data");
    await expect(detail.getByRole("row").filter({ hasText: "Maria Ortiz" })).toContainText("Only in civicpatch");
    await expect(detail).toContainText("Robert Smith is already matched to row 2");
  });

  test("a field's count lists its people with values tinted by side", async ({ maintainerPage: page }) => {
    await page.goto(PAGE);
    await page.getByRole("row").filter({ hasText: "Emails" }).locator(".rc-count").first().click();

    const list = page.locator(".rc-field-list");
    await expect(list).toContainText("Emails: one side has more");
    await expect(list.locator(".rc-table .rc-value--civicpatch-only")).toHaveText("clerk@e2e.gov");
    await expect(list.locator(".rc-table .rc-value--shared").first()).toHaveText("jane@e2e.gov");
  });

  test("an outcome's count lists those people across the state", async ({ maintainerPage: page }) => {
    await page.goto(PAGE);
    await page.locator(".rc-legend li").filter({ hasText: "Only in civicpatch" }).locator(".rc-count").click();

    const list = page.locator(".rc-field-list");
    await expect(list).toContainText("Only in civicpatch, across the state");
    await expect(list.getByRole("row").filter({ hasText: "Maria Ortiz" })).toBeVisible();
  });

  test("unticking an organization counts its civicpatch-only people apart", async ({ maintainerPage: page }) => {
    await page.goto(PAGE);
    const council = page.getByRole("checkbox", { name: /Town Council/ });
    const library = page.getByRole("checkbox", { name: /Library Board/ });
    await expect(council).toBeChecked();
    await expect(library).toBeChecked();
    await expect(page.locator(".rc-organization").filter({ hasText: "Town Council" })).toContainText(
      "1 matched of 2, in 1 jurisdiction",
    );

    await council.uncheck();

    await expect(page.locator(".rc-legend")).toContainText("Only in civicpatch 0");
    await expect(page.getByText("Not counted: 1 more of civicpatch's people")).toBeVisible();
    await expect(page.locator(".rc-legend")).toContainText("Matched 1");
  });

  test("with every organization deselected, only the list is left", async ({ maintainerPage: page }) => {
    await page.goto(PAGE);

    await page.getByRole("button", { name: "Deselect all", exact: true }).click();

    await expect(page.getByRole("checkbox", { name: /Town Council/ })).not.toBeChecked();
    await expect(page.locator(".rc-legend")).toHaveCount(0);
    await expect(page.locator(".rc-jurisdiction")).toHaveCount(0);

    await page.getByRole("button", { name: "Select all", exact: true }).click();

    await expect(page.locator(".rc-legend")).toContainText("Only in civicpatch 1");
  });

  test("the state's jurisdictions not in the uploaded data open into a list", async ({ maintainerPage: page }) => {
    await page.goto(PAGE);
    const notCompared = page.locator(".rc-not-compared");

    await notCompared.locator("summary").click();

    await expect(notCompared.locator(".rc-not-compared__list li").first()).toBeVisible();
  });

  test("a row's uploaded values open on keyboard focus", async ({ maintainerPage: page }) => {
    await page.goto(PAGE);
    await page.locator(".rc-jurisdiction").click();
    const rowRef = page.locator(".rc-jurisdiction-detail .rc-row-ref").first();

    await rowRef.focus();

    await expect(rowRef.locator(".rc-row-ref__popup")).toBeVisible();
    await expect(rowRef.locator(".rc-row-ref__popup")).toContainText("Row 2 as uploaded");
  });

  test("is closed to a signed-in user below maintainer", async ({ authenticatedPage: page }) => {
    await page.goto(PAGE);

    await expect(page).toHaveURL("/");
  });
});
