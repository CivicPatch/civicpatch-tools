/**
 * The scale card (spec §20) — a realistically-sized council.
 *
 * Every other fixture here holds two or three people, which makes the questions
 * the redesign exists to answer unfalsifiable: does the collapse rule earn its
 * keep, does the rail become an unusable scroll, does the grid hold at density.
 * This card is 38 existing against 40 proposed — 3 dropped, 5 added, 10 changed,
 * 25 untouched.
 *
 * These tests assert the fixture seeds the composition it claims. That matters
 * before the layout work: a scale fixture nobody checks is 80 lines of builder
 * that silently drifts, and every later assertion about density rests on it.
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_REQUEST_ID } from "../fixtures/db.js";

test.describe("Review card at scale", () => {
  test("seeds the composition the layout work needs", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?request_id=${SCALE_REQUEST_ID}`);
    await expect(page.locator("people-diff")).toBeVisible();

    // 35 carried over + 5 added, and the 3 the scrape dropped still get a card.
    await expect(page.locator(".people-diff__person")).toHaveCount(43);

    const count = (key) =>
      page.locator(`.people-diff__chip--${key} .people-diff__chip-count`);
    await expect(count("changed")).toHaveText("10");
    await expect(count("added")).toHaveText("5");
    await expect(count("removed")).toHaveText("3");
    await expect(count("unchanged")).toHaveText("25");
  });

  test("carries anchored and person-level issues at density", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?request_id=${SCALE_REQUEST_ID}`);
    await expect(page.locator("people-diff")).toBeVisible();

    // A field-anchored issue on two holders — the case the collapse rule's
    // rule 2 exists for, since office.name is unchanged on both.
    await expect(
      page.locator(".people-diff__issue").filter({ hasText: "council president" }),
    ).toHaveCount(2);

    // And a person-level one, which anchors to no field.
    await expect(
      page.locator(".people-diff__issue").filter({ hasText: "Extra official" }),
    ).toHaveCount(1);
  });
});
