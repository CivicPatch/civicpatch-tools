/**
 * The person editor (spec §5), reached by opening someone from the roster
 * remains the default.
 *
 * The collapse rule is the whole point of the redesign, so that is what these
 * assert: an unchanged person shows no field rows at all, a changed one shows
 * only what moved, and everything else hides behind an expander that says how
 * much it is hiding.
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_CHANGESET_ID } from "../fixtures/db.js";
import { actionsFor, openEditorFor } from "./helpers/review-card.js";

// The editor lives in the modal now — there are no view tabs, and a person is opened from
// their row on the roster.
const openEditor = async (page, changesetId, name) => {
  await page.goto(`/review/session?changeset_id=${changesetId}`);
  await expect(page.locator("review-overview")).toBeVisible();
  await openEditorFor(page, name);
};

const editorFor = (page, name) =>
  page
    .locator(".person-editor")
    .filter({ has: page.locator(".person-editor__name", { hasText: name }) });

test.describe("Review person editor", () => {
  test("a person with nothing to review is one line, not a card", async ({
    authenticatedPage: page,
  }) => {
    await openEditor(page, SCALE_CHANGESET_ID, "Councillor 03 Scale");

    // Councillor 03 is one of the 25 the scrape returned identically.
    const editor = editorFor(page, "Councillor 03 Scale");
    await expect(editor).toHaveClass(/person-editor--strip/);
    await expect(editor.locator(".person-editor__field")).toHaveCount(0);

    // Their fields are still reachable — the roster reads complete without
    // spending a card on someone who has nothing to say.
    await editor.locator(".person-editor__expander").click();
    await expect(editor.locator(".person-editor__field")).toHaveCount(10);
  });

  test("a changed person shows only what moved, plus its evidence", async ({
    authenticatedPage: page,
  }) => {
    await openEditor(page, SCALE_CHANGESET_ID, "Councillor 13 Scale");

    // The fixture rotates change shapes by index; 13 is the one that only
    // gained an email. (02 changes its term end AND clears its phone — two
    // fields — which is worth having as the multi-change case below.)
    //
    // Two rows, not one: Source urls is a context field (`diff: false`), so it
    // is always visible as the evidence for the change and never itself a
    // reason to review. Everything else still hides.
    // Source urls carries the required marker, same as Name and Office.
    const editor = editorFor(page, "Councillor 13 Scale");
    await expect(editor.locator(".person-editor__label")).toHaveText([
      "Email",
      "Source urls *",
    ]);
  });

  test("the expander reveals the rest and puts them back", async ({
    authenticatedPage: page,
  }) => {
    await openEditor(page, SCALE_CHANGESET_ID, "Councillor 02 Scale");

    // 02 changed its term end and cleared its phone, so two rows survive and
    // the other nine hide.
    // Three rows: the two that moved, plus the always-visible Source urls.
    const editor = editorFor(page, "Councillor 02 Scale");
    await expect(editor.locator(".person-editor__field")).toHaveCount(3);
    await expect(editor.locator(".person-editor__expander")).toContainText(
      "7 unchanged fields",
    );

    await editor.locator(".person-editor__expander").click();
    await expect(editor.locator(".person-editor__field")).toHaveCount(10);

    await editor.locator(".person-editor__expander").click();
    await expect(editor.locator(".person-editor__field")).toHaveCount(3);
  });

  test("a person the scrape dropped is one decision, not eleven fields", async ({
    authenticatedPage: page,
  }) => {
    await openEditor(page, SCALE_CHANGESET_ID, "Councillor 36 Scale");

    const editor = editorFor(page, "Councillor 36 Scale");
    await expect(editor).toHaveClass(/person-editor--removed/);
    await expect(editor.locator(".person-editor__banner-title")).toContainText(
      "Not found in this scrape",
    );
    // Their details are available, but not spent by default.
    await expect(editor.locator(".person-editor__field")).toHaveCount(0);
    await expect(
      actionsFor(page, "Councillor 36 Scale").locator(
        ".person-editor__restore-person",
      ),
    ).toBeVisible();
  });
});

test.describe("Review editor — multi-value provenance (§5.2)", () => {
  // Councillor 13 gained a second email; nothing else about them moved.
  // The Email row specifically. Councillor 13's editor also carries the
  // always-visible Source urls row, which is a multi-value field too — matching
  // every field row would count its inputs as well.
  // Every list renders one more row than it holds — the trailing empty one is how
  // a value is added — so counting inputs without excluding it counts a value
  // that is not there.
  const valueInputs = (field) =>
    field.locator(
      "input.field-control__input:not(.field-control__input--draft)",
    );

  // The row for a value the scrape stopped listing: shown struck through, with a
  // Put back action instead of an input.
  const droppedRow = (field) =>
    field.locator(
      ".field-control__multi-row:has(.field-control__input--cleared)",
    );

  const emailField = (page) =>
    page
      .locator(".person-editor")
      .filter({
        has: page.locator(".person-editor__name", {
          hasText: "Councillor 13 Scale",
        }),
      })
      .locator(".person-editor__field")
      .filter({ hasText: "Email" });

  test("marks the value the scrape added, and leaves the kept one unmarked", async ({
    authenticatedPage: page,
  }) => {
    await openEditor(page, SCALE_CHANGESET_ID, "Councillor 13 Scale");
    const field = emailField(page);

    // One list, not two columns: both addresses are editable rows.
    await expect(valueInputs(field)).toHaveCount(2);
    // Provenance is a marker on the row the scrape added; the kept one carries
    // none, so exactly one is marked.
    await expect(
      field.locator('input[title="Found by this scrape"]'),
    ).toHaveCount(1);
  });

  test("a value the scrape lost reads as dropped and comes back one at a time", async ({
    authenticatedPage: page,
  }) => {
    await openEditor(page, SCALE_CHANGESET_ID, "Councillor 02 Scale");
    // Councillor 02 had its phone cleared, so that value is dropped, not gone.
    const phone = page
      .locator(".person-editor")
      .filter({
        has: page.locator(".person-editor__name", {
          hasText: "Councillor 02 Scale",
        }),
      })
      .locator(".person-editor__field")
      .filter({ hasText: "Phone" });

    const dropped = droppedRow(phone);
    await expect(dropped).toHaveCount(1);
    // Struck through, so it reads as what the scrape stopped listing.
    await expect(dropped.locator("s")).toHaveCount(1);
    // Not an input — it is the record of what was lost, not something to edit.
    await expect(dropped.locator("input")).toHaveCount(0);

    await dropped.locator(".field-control__action--restore").click();

    // Restoring moves that one value into the editable list, and nothing is
    // dropped any more — so the field stops reading as changed.
    await expect(droppedRow(phone)).toHaveCount(0);
    await expect(valueInputs(phone)).toHaveCount(1);
  });

  test("provenance is derived, so retyping a dropped value clears its chip", async ({
    authenticatedPage: page,
  }) => {
    await openEditor(page, SCALE_CHANGESET_ID, "Councillor 02 Scale");
    const phone = page
      .locator(".person-editor")
      .filter({
        has: page.locator(".person-editor__name", {
          hasText: "Councillor 02 Scale",
        }),
      })
      .locator(".person-editor__field")
      .filter({ hasText: "Phone" });

    await expect(droppedRow(phone)).toHaveCount(1);

    // Type the dropped number back in by hand rather than clicking Put back. If
    // provenance were stamped when a row was made, the dropped row would linger
    // beside its own value. Typing into the trailing empty row is the add — there
    // is no button.
    await phone
      .locator("input.field-control__input--draft")
      .fill("(201) 555-0102");
    await expect(droppedRow(phone)).toHaveCount(0);
  });
});
