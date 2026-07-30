/**
 * Preview (spec §7) — what publishing produces, and the gate on doing it.
 *
 * Preview carries no diff vocabulary: it answers "what will the site say about
 * this council", so what the scrape did to get there is not part of it. The
 * publish gate lives here too, because §9 drives the button and this banner from
 * one function — they cannot disagree about whether the card is publishable.
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_REQUEST_ID, RECONCILE_REQUEST_ID } from "../fixtures/db.js";
import { openDetail, railFor, fieldIn } from "./helpers/review-card.js";

const openPreview = async (page, requestId = SCALE_REQUEST_ID) => {
  await page.goto(`/review/session?request_id=${requestId}&view=preview`);
  await expect(page.locator("review-preview")).toBeVisible();
};

test.describe("Review preview", () => {
  test("shows exactly the publish payload", async ({ authenticatedPage: page }) => {
    await openPreview(page);

    // 35 carried over + 5 added. The 3 the scrape dropped have no record, so
    // they are already absent — the same filter buildPeoplePatch applies.
    await expect(page.locator(".review-preview__card")).toHaveCount(40);
    await expect(page.locator(".review-preview__bar")).toContainText("40 officials");
    await expect(page.locator(".review-preview__bar")).toContainText("5 new · 3 dropped");
  });

  test("drops someone the reviewer removed, live", async ({ authenticatedPage: page }) => {
    await page.goto(`/review/session?request_id=${SCALE_REQUEST_ID}`);
    await openDetail(page);
    await railFor(page, "Councillor 02 Scale").locator(".review-rail__delete").click();

    await page.locator(".review-page__view-tab", { hasText: "Preview" }).click();
    await expect(page.locator(".review-preview__card")).toHaveCount(39);
    await expect(page.locator(".review-preview__bar")).toContainText("4 dropped");
  });

  test("carries no diff vocabulary", async ({ authenticatedPage: page }) => {
    await openPreview(page);

    // No state colours, no strikethrough, no attention icons — even though the
    // very same cards render all three in Detail.
    await expect(page.locator(".review-preview del")).toHaveCount(0);
    await expect(page.locator(".review-preview .review-rail__issue")).toHaveCount(0);
    await expect(page.locator(".review-preview .review-tile__badge")).toHaveCount(0);
  });

  test("sorts by seat, at-large first", async ({ authenticatedPage: page }) => {
    await openPreview(page, RECONCILE_REQUEST_ID);
    // The reconcile fixture has no divisions at all, so everyone is at-large and
    // the order is stable rather than arbitrary.
    await expect(page.locator(".review-preview__card")).toHaveCount(2);
  });
});

test.describe("Publish gating", () => {
  test("a blocking error disables Publish and says what to fix", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?request_id=${SCALE_REQUEST_ID}`);
    await openDetail(page);

    // Clear a required field on someone being published.
    const rail = railFor(page, "Councillor 02 Scale");
    await rail.locator(".review-rail__expander").click();
    await fieldIn(rail, "Name").first().locator("input").fill("");

    const publish = page.locator(".review-page__publish-btn");
    await expect(publish).toBeDisabled();
    await expect(publish).toContainText("to fix before publishing");

    // Save for later is never gated — parking incomplete work is what it is for.
    await expect(page.locator(".review-page__save-btn")).toBeEnabled();
  });

  test("the banner and the button agree, because one function drives both", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?request_id=${SCALE_REQUEST_ID}`);
    await openDetail(page);
    const rail = railFor(page, "Councillor 02 Scale");
    await rail.locator(".review-rail__expander").click();
    await fieldIn(rail, "Name").first().locator("input").fill("");

    await page.locator(".review-page__view-tab", { hasText: "Preview" }).click();
    await expect(page.locator(".review-preview__blockers")).toContainText("Name: Required");
    await expect(page.locator(".review-page__publish-btn")).toBeDisabled();
  });

  test("a blocker on someone being dropped does not gate publishing", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?request_id=${SCALE_REQUEST_ID}`);
    await openDetail(page);
    // Office rather than Name: clearing the name would invalidate the locator
    // that finds this rail, since it matches on the name header. Office is
    // unchanged on this person, so the collapse rule hides it until expanded.
    const rail = railFor(page, "Councillor 02 Scale");
    await rail.locator(".review-rail__expander").click();
    await fieldIn(rail, "Office").first().locator("input").fill("");
    await expect(page.locator(".review-page__publish-btn")).toBeDisabled();

    // Dropping them makes the error irrelevant — it is not part of the payload.
    await rail.locator(".review-rail__delete").click();
    await expect(page.locator(".review-page__publish-btn")).toBeEnabled();
  });
});
