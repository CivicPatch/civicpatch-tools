/**
 * User story: a maintainer edits a roster where one person sits in two bodies.
 *
 * This is the §20 manual check of the projector plan, written down. The grouping and the
 * payload are unit-tested (tests/roster-organization-grouping.test.ts,
 * tests/roster-edit-payload.test.ts); what only a browser can answer is whether the page
 * actually puts that person under both sections, keeps the two rows independent, and lets a
 * removal take one of them. Until 2026-09-23 the page filed anyone holding two offices under
 * whichever body sorted first, so the second section simply did not list them.
 *
 * Seeded, not stubbed: the roster comes from `dbFixtures` and is answered by the real
 * endpoint, so this also catches the read's shape drifting. Publishing is deliberately not
 * exercised — it writes claims to the shared test database, and what it would prove (one
 * body's office surviving an edit to the other) is pinned in `roster-edit-payload.test.ts`.
 */

import { test, expect } from "../fixtures/index.js";
import {
  TWO_BODY_JURISDICTION_OCDID,
  TWO_BODY_COUNCIL,
  TWO_BODY_SCHOOL_BOARD,
} from "../fixtures/db.js";

const ADA = "Ada Two-Body";
const BO = "Bo Council-Only";

const section = (page, name) =>
  page.locator("section.panel").filter({ has: page.locator(`.panel__cap b:text-is("${name}")`) });

const row = (page, name, person) =>
  section(page, name).locator(".rperson").filter({ hasText: person });

test.describe("Roster editor — one person, two bodies", () => {
  test.beforeEach(async ({ maintainerPage: page }) => {
    const people = page.waitForResponse(/\/api\/v1\/people\?/);
    await page.goto(`/${TWO_BODY_JURISDICTION_OCDID}`);
    await people;
  });

  test("lists the same person under every body they hold an office in", async ({
    maintainerPage: page,
  }) => {
    await expect(row(page, TWO_BODY_COUNCIL, ADA)).toHaveCount(1);
    await expect(row(page, TWO_BODY_SCHOOL_BOARD, ADA)).toHaveCount(1);
    // The neighbour who sits in one body only, so "under both" means something.
    await expect(row(page, TWO_BODY_COUNCIL, BO)).toHaveCount(1);
    await expect(row(page, TWO_BODY_SCHOOL_BOARD, BO)).toHaveCount(0);
  });

  test("opening one of their rows does not open the other", async ({
    maintainerPage: page,
  }) => {
    await row(page, TWO_BODY_COUNCIL, ADA).click();

    await expect(page.locator(".person-editor-inline")).toHaveCount(1);
    await expect(
      section(page, TWO_BODY_COUNCIL).locator(".person-editor-inline"),
    ).toHaveCount(1);
    await expect(
      section(page, TWO_BODY_SCHOOL_BOARD).locator(".person-editor-inline"),
    ).toHaveCount(0);
  });

  test("removing them from one body leaves the other body's row alone", async ({
    maintainerPage: page,
  }) => {
    const publish = page.locator(".roster-header .btn-primary");
    await expect(publish).toBeDisabled();

    await row(page, TWO_BODY_COUNCIL, ADA).click();
    await page.locator(".person-editor__delete").click();

    // A removal is staged, not sent: it goes out with Publish, which is what enables here.
    await expect(publish).toBeEnabled();
    // The row that was pressed now offers to undo itself.
    await expect(
      section(page, TWO_BODY_COUNCIL).locator(".person-editor__restore-person"),
    ).toHaveCount(1);

    // The school board row is untouched: opening it still offers Remove, not Restore.
    await row(page, TWO_BODY_SCHOOL_BOARD, ADA).click();
    await expect(
      section(page, TWO_BODY_SCHOOL_BOARD).locator(".person-editor__delete"),
    ).toHaveCount(1);
    await expect(
      section(page, TWO_BODY_SCHOOL_BOARD).locator(".person-editor__restore-person"),
    ).toHaveCount(0);
  });
});
