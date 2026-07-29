/**
 * User story: reviewing a re-scrape shows what moved, and lets you edit it.
 *
 * Given a previously-scraped jurisdiction with existing people
 * And a proposed set that changes one, adds one, and drops one
 * When I open its review card
 * Then the rail shows each person's changed / added / removed state
 * And only the fields that actually moved
 * And editing one recomputes the card live
 *
 * Rewritten from the people-diff era. That component rendered every field for
 * every person in an `old | copy | new` grid, so its assertions were about the
 * two columns — which value sat on which side, and whether the copy arrow moved
 * one to the other. The rail replaced that with `label | control | was …
 * Restore` and the collapse rule, so the same claims are now made about which
 * rows exist at all and what their trailing annotation says.
 */

import { test, expect } from "../fixtures/index.js";
import { RECONCILE_REQUEST_ID } from "../fixtures/db.js";
import { openDetail, railFor, fieldIn } from "./helpers/review-card.js";

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
    const maria = railFor(page, "Maria González");
    await expect(maria).toHaveClass(/review-rail--changed/);

    // Office changed, an email was added, a phone was cleared — and Division is
    // here for a different reason: the fixture has division_ocdid null on BOTH
    // sides, so it reads `same` to a pure diff while still blocking publish.
    // That is rule 3 of the collapse rule (§2), and the row is exactly what
    // stops the card hiding why publishing fails. Everything else moved by
    // nothing and is not on screen — which the old view could not do, since it
    // rendered all eleven fields regardless.
    await expect(maria.locator(".review-rail__field")).toHaveCount(4);
    await expect(maria.locator(".review-rail__label")).toHaveText([
      "Office *",
      "Division *",
      "Email",
      "Phone",
    ]);
    await expect(
      fieldIn(maria, "Division").locator(".review-rail__error"),
    ).toContainText("Required");

    // The office control carries the new value; the old one is a trailing
    // annotation rather than a second column.
    const office = fieldIn(maria, "Office");
    await expect(office.locator("input")).toHaveValue("Council Member");
    await expect(office.locator(".review-rail__was")).toContainText("was Mayor");

    // Added-only and removed-only people each get their own rail.
    await expect(railFor(page, "Tom Treasurer")).toHaveClass(/review-rail--added/);
    await expect(railFor(page, "Bob Clerk")).toHaveClass(/review-rail--removed/);
  });

  test("a person the scrape dropped is one decision, not a column of dashes", async ({
    authenticatedPage: page,
  }) => {
    await openCard(page);

    // The old view rendered their every field as `old (struck) → "—"`. §5 says
    // the card is one decision, so the fields collapse behind an expander.
    const bob = railFor(page, "Bob Clerk");
    await expect(bob.locator(".review-rail__banner-title")).toContainText(
      "Not found in this scrape",
    );
    await expect(bob.locator(".review-rail__field")).toHaveCount(0);
    await expect(bob.locator(".review-rail__restore-person")).toBeVisible();
  });

  test("editing recomputes the card live", async ({ authenticatedPage: page }) => {
    await openCard(page);
    const maria = railFor(page, "Maria González");
    const office = fieldIn(maria, "Office");

    // Setting Office back to its old value clears the change: the `was`
    // annotation has nothing left to say and goes away. The row itself stays —
    // fields never leave a card once shown (§2.1).
    await office.locator("input").fill("Mayor");
    await expect(office.locator(".review-rail__was")).toHaveCount(0);
    await expect(maria.locator(".review-rail__field")).toHaveCount(4);
  });

  test("Restore puts the old value back", async ({ authenticatedPage: page }) => {
    await openCard(page);
    const office = fieldIn(railFor(page, "Maria González"), "Office");

    // Replaces the old copy-arrow: same claim — one click moves the old value
    // into the control — in the shape the rail uses.
    await office.locator(".review-rail__restore").click();
    await expect(office.locator("input")).toHaveValue("Mayor");
  });

  test("dates are edited through Year / Month / Day, which cannot be malformed", async ({
    authenticatedPage: page,
  }) => {
    await openCard(page);
    const maria = railFor(page, "Maria González");

    // Term start is "2021" on both sides, so the collapse rule hides it — the
    // expander is how you reach a field that did not move.
    await maria.locator(".review-rail__expander").click();
    const termStart = fieldIn(maria, "Term start").first();

    await expect(termStart.locator(".people-diff__date-year")).toHaveValue("2021");
    const month = termStart.locator('select[aria-label="Month"]');
    const day = termStart.locator('select[aria-label="Day"]');
    await expect(month).toHaveValue("");
    await expect(day).toBeDisabled();

    // Picking a month round-trips to "2021-03" and the field starts saying so.
    await month.selectOption("03");
    await expect(termStart.locator(".review-rail__was")).toContainText("was 2021");
    await expect(day).toBeEnabled();

    // Clearing the month drops back to the bare year, and takes any day with it.
    await day.selectOption("15");
    await month.selectOption("");
    await expect(day).toBeDisabled();
    await expect(day).toHaveValue("");
  });

  test("links an added person to a removed record", async ({
    authenticatedPage: page,
  }) => {
    await openCard(page);

    await expect(railFor(page, "Tom Treasurer")).toHaveClass(/review-rail--added/);
    await expect(railFor(page, "Bob Clerk")).toHaveClass(/review-rail--removed/);

    // Link Tom → Bob via the picker on Tom's rail (value is Bob's fixture id).
    await railFor(page, "Tom Treasurer").locator(".review-rail__link").selectOption("recon-bob");

    // Bob's own rail is gone; Tom now pairs as a single CHANGED person.
    await expect(railFor(page, "Bob Clerk")).toHaveCount(0);
    const linked = railFor(page, "Tom Treasurer");
    await expect(linked).toHaveClass(/review-rail--changed/);

    // The old name is folded into other_names so the next scrape matches, and
    // the name field now says what it was.
    await expect(fieldIn(linked, "Name").locator(".review-rail__was")).toContainText(
      "was Bob Clerk",
    );
    await expect(
      fieldIn(linked, "Other names").locator("input").first(),
    ).toHaveValue("Bob Clerk");
  });
});