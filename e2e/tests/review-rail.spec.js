/**
 * Detail v2 — the rail (spec §5), reachable at ?view=detail while the old diff
 * remains the default.
 *
 * The collapse rule is the whole point of the redesign, so that is what these
 * assert: an unchanged person shows no field rows at all, a changed one shows
 * only what moved, and everything else hides behind an expander that says how
 * much it is hiding.
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_REQUEST_ID, RECONCILE_REQUEST_ID } from "../fixtures/db.js";

const openRail = async (page, requestId) => {
  await page.goto(`/review/session?request_id=${requestId}&view=detail`);
  await expect(page.locator("review-rail-list")).toBeVisible();
};

const railFor = (page, name) =>
  page
    .locator(".review-rail")
    .filter({ has: page.locator(".review-rail__name", { hasText: name }) });

test.describe("Review rail (Detail v2)", () => {
  test("a card opens on Overview; ?view=detail opens the rail", async ({
    authenticatedPage: page,
  }) => {
    // Previously this asserted that the default still rendered people-diff,
    // which described the interim state while both existed. §1.1 makes Overview
    // the default and people-diff is gone.
    await page.goto(`/review/session?request_id=${RECONCILE_REQUEST_ID}`);
    await expect(page.locator("review-overview")).toBeVisible();
    await expect(page.locator("review-rail-list")).toHaveCount(0);

    await openRail(page, RECONCILE_REQUEST_ID);
    await expect(page.locator("review-overview")).toHaveCount(0);
  });

  test("switching view writes ?view=, and a reload lands back there", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?request_id=${RECONCILE_REQUEST_ID}`);
    await page.locator(".review-page__view-tab", { hasText: "Detail" }).click();
    await expect(page).toHaveURL(/view=detail/);

    await page.reload();
    await expect(page.locator("review-rail-list")).toBeVisible();
  });

  test("a person with nothing to review is one line, not a card", async ({
    authenticatedPage: page,
  }) => {
    await openRail(page, SCALE_REQUEST_ID);

    // Councillor 03 is one of the 25 the scrape returned identically.
    const rail = railFor(page, "Councillor 03 Scale");
    await expect(rail).toHaveClass(/review-rail--strip/);
    await expect(rail.locator(".review-rail__field")).toHaveCount(0);

    // Their fields are still reachable — the roster reads complete without
    // spending a card on someone who has nothing to say.
    await rail.locator(".review-rail__expander").click();
    await expect(rail.locator(".review-rail__field")).toHaveCount(11);
  });

  test("a changed person shows only what moved, plus its evidence", async ({
    authenticatedPage: page,
  }) => {
    await openRail(page, SCALE_REQUEST_ID);

    // The fixture rotates change shapes by index; 13 is the one that only
    // gained an email. (02 changes its term end AND clears its phone — two
    // fields — which is worth having as the multi-change case below.)
    //
    // Two rows, not one: Source urls is a context field (`diff: false`), so it
    // is always visible as the evidence for the change and never itself a
    // reason to review. Everything else still hides.
    const rail = railFor(page, "Councillor 13 Scale");
    await expect(rail.locator(".review-rail__label")).toHaveText([
      "Email",
      "Source urls",
    ]);
  });

  test("the expander reveals the rest and puts them back", async ({
    authenticatedPage: page,
  }) => {
    await openRail(page, SCALE_REQUEST_ID);

    // 02 changed its term end and cleared its phone, so two rows survive and
    // the other nine hide.
    // Three rows: the two that moved, plus the always-visible Source urls.
    const rail = railFor(page, "Councillor 02 Scale");
    await expect(rail.locator(".review-rail__field")).toHaveCount(3);
    await expect(rail.locator(".review-rail__expander")).toContainText("8 unchanged fields");

    await rail.locator(".review-rail__expander").click();
    await expect(rail.locator(".review-rail__field")).toHaveCount(11);

    await rail.locator(".review-rail__expander").click();
    await expect(rail.locator(".review-rail__field")).toHaveCount(3);
  });

  test("a person the scrape dropped is one decision, not eleven fields", async ({
    authenticatedPage: page,
  }) => {
    await openRail(page, SCALE_REQUEST_ID);

    const rail = railFor(page, "Councillor 36 Scale");
    await expect(rail).toHaveClass(/review-rail--removed/);
    await expect(rail.locator(".review-rail__banner-title")).toContainText(
      "Not found in this scrape",
    );
    // Their details are available, but not spent by default.
    await expect(rail.locator(".review-rail__field")).toHaveCount(0);
    await expect(rail.locator(".review-rail__restore-person")).toBeVisible();
  });
});

test.describe("Review rail — multi-value provenance (§5.2)", () => {
  // Councillor 13 gained a second email; nothing else about them moved.
  // The Email row specifically. Councillor 13's rail also carries the
  // always-visible Source urls row, which is a multi-value field too — matching
  // every field row would count its inputs as well.
  const emailField = (page) =>
    page
      .locator(".review-rail")
      .filter({ has: page.locator(".review-rail__name", { hasText: "Councillor 13 Scale" }) })
      .locator(".review-rail__field")
      .filter({ hasText: "Email" });

  test("marks the value the scrape added, and leaves the kept one unmarked", async ({
    authenticatedPage: page,
  }) => {
    await openRail(page, SCALE_REQUEST_ID);
    const field = emailField(page);

    // One list, not two columns: both addresses are editable rows.
    await expect(field.locator(".field-control__multi-row input")).toHaveCount(2);
    await expect(field.locator(".field-control__provenance")).toHaveText(["new"]);
  });

  test("a value the scrape lost reads as dropped and comes back one at a time", async ({
    authenticatedPage: page,
  }) => {
    await openRail(page, SCALE_REQUEST_ID);
    // Councillor 02 had its phone cleared, so that value is dropped, not gone.
    const phone = page
      .locator(".review-rail")
      .filter({ has: page.locator(".review-rail__name", { hasText: "Councillor 02 Scale" }) })
      .locator(".review-rail__field")
      .filter({ hasText: "Phone" });

    const droppedRow = phone.locator(".field-control__multi-row--dropped");
    await expect(droppedRow).toHaveCount(1);
    await expect(droppedRow.locator(".field-control__provenance")).toHaveText("dropped");
    // Not an input — it is the record of what was lost, not something to edit.
    await expect(droppedRow.locator("input")).toHaveCount(0);

    await droppedRow.locator(".field-control__restore-value").click();

    // Restoring moves that one value into the editable list, and nothing is
    // dropped any more — so the field stops reading as changed.
    await expect(phone.locator(".field-control__multi-row--dropped")).toHaveCount(0);
    await expect(phone.locator(".field-control__multi-row input")).toHaveCount(1);
  });

  test("provenance is derived, so retyping a dropped value clears its row", async ({
    authenticatedPage: page,
  }) => {
    await openRail(page, SCALE_REQUEST_ID);
    const phone = page
      .locator(".review-rail")
      .filter({ has: page.locator(".review-rail__name", { hasText: "Councillor 02 Scale" }) })
      .locator(".review-rail__field")
      .filter({ hasText: "Phone" });

    await expect(phone.locator(".field-control__multi-row--dropped")).toHaveCount(1);

    // Type the dropped number back in by hand rather than clicking Restore. If
    // provenance were stamped when a row was made, the dropped row would linger
    // beside its own value.
    await phone.locator(".field-control__add").click();
    await phone.locator(".field-control__multi-row input").last().fill("(555) 020-0102");
    await expect(phone.locator(".field-control__multi-row--dropped")).toHaveCount(0);
  });
});
