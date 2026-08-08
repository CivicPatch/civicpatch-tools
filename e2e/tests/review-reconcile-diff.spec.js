/**
 * User story: reviewing a re-scrape shows what moved, and lets you edit it.
 *
 * Given a previously-scraped jurisdiction with existing people
 * And a proposed set that changes one, adds one, and drops one
 * When I open its review card
 * Then the editor shows each person's changed / added / removed state
 * And only the fields that actually moved
 * And editing one recomputes the card live
 *
 * Rewritten from the people-diff era. That component rendered every field for
 * every person in an `old | copy | new` grid, so its assertions were about the
 * two columns — which value sat on which side, and whether the copy arrow moved
 * one to the other. The editor replaced that with `label | control | was …
 * Restore` and the collapse rule, so the same claims are now made about which
 * rows exist at all and what their trailing annotation says.
 */

import { test, expect } from "../fixtures/index.js";
import { RECONCILE_REQUEST_ID } from "../fixtures/db.js";
import { openDetail, editorFor, fieldIn } from "./helpers/review-card.js";

const openCard = async (page) => {
  await page.goto(`/review/session?request_id=${RECONCILE_REQUEST_ID}`);
  await openDetail(page);
};

test.describe("Review reconcile diff (populated)", () => {
  test("shows each person's state, and only the fields that moved", async ({
    authenticatedPage: page,
  }) => {
    await openCard(page);

    // Maria pairs as CHANGED — guards the existing<->new id pairing.
    const maria = editorFor(page, "Maria González");
    await expect(maria).toHaveClass(/person-editor--changed/);

    // Office changed, an email was added, a phone was cleared. Nothing else
    // moved, so nothing else is on screen — which the old view could not do,
    // since it rendered all eleven fields regardless.
    //
    // The fourth row is Source urls, and it is not a change: `diff: false` makes
    // it a context field, always visible as the evidence behind the other three
    // and never itself a reason to review.
    //
    // A different fourth row appeared here once before and was a genuine fault:
    // the fixture had division_ocdid null on both sides, which reads `same` to a
    // pure diff but is required, so rule 3 surfaced it. The publish gate then
    // refused to publish the fixture at all, which is how we noticed the data
    // was impossible — resolve_division always returns a division. The fixture
    // now carries one. Naming the rows rather than counting them is what tells
    // those two cases apart.
    await expect(maria.locator(".person-editor__label")).toHaveText([
      "Office *",
      "Email",
      "Phone",
      "Source urls",
    ]);

    // The office control carries the new value; the old one is a trailing
    // annotation rather than a second column.
    const office = fieldIn(maria, "Office");
    await expect(office.locator("input")).toHaveValue("Council Member");
    await expect(office.locator(".person-editor__was")).toContainText("was Mayor");

    // Added-only and removed-only people each get their own editor.
    await expect(editorFor(page, "Tom Treasurer")).toHaveClass(/person-editor--added/);
    await expect(editorFor(page, "Bob Clerk")).toHaveClass(/person-editor--removed/);
  });

  test("a person the scrape dropped is one decision, not a column of dashes", async ({
    authenticatedPage: page,
  }) => {
    await openCard(page);

    // The old view rendered their every field as `old (struck) → "—"`. §5 says
    // the card is one decision, so the fields collapse behind an expander.
    const bob = editorFor(page, "Bob Clerk");
    await expect(bob.locator(".person-editor__banner-title")).toContainText(
      "Not found in this scrape",
    );
    await expect(bob.locator(".person-editor__field")).toHaveCount(0);
    await expect(bob.locator(".person-editor__restore-person")).toBeVisible();
  });

  test("editing recomputes the card live", async ({ authenticatedPage: page }) => {
    await openCard(page);
    const maria = editorFor(page, "Maria González");
    const office = fieldIn(maria, "Office");

    // Setting Office back to its old value clears the change: the `was`
    // annotation has nothing left to say and goes away. The row itself stays —
    // fields never leave a card once shown (§2.1).
    await office.locator("input").fill("Mayor");
    await expect(office.locator(".person-editor__was")).toHaveCount(0);
    await expect(maria.locator(".person-editor__field")).toHaveCount(4);
  });

  test("Restore puts the old value back", async ({ authenticatedPage: page }) => {
    await openCard(page);
    const office = fieldIn(editorFor(page, "Maria González"), "Office");

    // Replaces the old copy-arrow: same claim — one click moves the old value
    // into the control — in the shape the editor uses.
    await office.locator(".person-editor__restore").click();
    await expect(office.locator("input")).toHaveValue("Mayor");
  });

  test("dates are edited through Year / Month / Day, which cannot be malformed", async ({
    authenticatedPage: page,
  }) => {
    await openCard(page);
    const maria = editorFor(page, "Maria González");

    // Term start is "2021" on both sides, so the collapse rule hides it — the
    // expander is how you reach a field that did not move.
    await maria.locator(".person-editor__expander").click();
    const termStart = fieldIn(maria, "Term start").first();

    await expect(termStart.locator(".field-control__date-year")).toHaveValue("2021");
    // Each select is named for the field it belongs to, not the part alone — a
    // card holds several dates, and a bare "Month" would not say whose.
    const month = termStart.locator('select[aria-label="Term start month"]');
    const day = termStart.locator('select[aria-label="Term start day"]');
    await expect(month).toHaveValue("");
    await expect(day).toBeDisabled();

    // Picking a month round-trips to "2021-03" and the field starts saying so.
    await month.selectOption("03");
    await expect(termStart.locator(".person-editor__was")).toContainText("was 2021");
    await expect(day).toBeEnabled();

    // Clearing the month drops back to the bare year, and takes any day with it.
    await day.selectOption("15");
    await month.selectOption("");
    await expect(day).toBeDisabled();
    await expect(day).toHaveValue("");
  });

  test("merges an added person into the record the scrape didn't find", async ({
    authenticatedPage: page,
  }) => {
    await openCard(page);

    await expect(editorFor(page, "Tom Treasurer")).toHaveClass(/person-editor--added/);
    await expect(editorFor(page, "Bob Clerk")).toHaveClass(/person-editor--removed/);

    // Step 1 is in place on the editor: the button opens the other people on this
    // card, and picking one opens the picker on that pair.
    const tom = editorFor(page, "Tom Treasurer");
    await tom.locator(".person-editor__merge").click();
    await tom
      .locator(".person-editor__merge-faces .review-face", { hasText: "Bob Clerk" })
      .click();

    // Bob survives, because his is the id the database already has — the commit
    // is worded in his direction even though the scrape's values win by default.
    // The commit button lives in the dialog footer now, not inside merge-picker —
    // inline actions scrolled out of reach on a long field list.
    await page
      .locator(".review-modal__foot button", { hasText: "Merge into Bob Clerk" })
      .click();

    // Bob's own editor is gone; the pair is a single CHANGED person.
    await expect(editorFor(page, "Bob Clerk")).toHaveCount(0);
    const linked = editorFor(page, "Tom Treasurer");
    await expect(linked).toHaveClass(/person-editor--changed/);

    // The old name is folded into other_names so the next scrape matches, and
    // the name field now says what it was.
    await expect(fieldIn(linked, "Name").locator(".person-editor__was")).toContainText(
      "was Bob Clerk",
    );
    await expect(
      fieldIn(linked, "Other names").locator("input").first(),
    ).toHaveValue("Bob Clerk");
  });
});