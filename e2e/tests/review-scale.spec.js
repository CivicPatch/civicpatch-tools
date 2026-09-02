/**
 * The scale card (spec §20) — a realistically-sized council.
 *
 * Every other fixture here holds two or three people, which makes the questions
 * the redesign exists to answer unfalsifiable: does the collapse rule earn its
 * keep, does the editor become an unusable scroll, does the grid hold at density.
 * This card is 38 existing against 40 proposed — 3 dropped, 5 added, 10 changed,
 * 25 untouched.
 *
 * These tests assert the fixture seeds the composition it claims. That matters
 * before the layout work: a scale fixture nobody checks is 80 lines of builder
 * that silently drifts, and every later assertion about density rests on it.
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_CHANGESET_ID } from "../fixtures/db.js";
import { openEditorFor, editorFor } from "./helpers/review-card.js";

// The scrape promotes these five to Council President — a role marked unique, so each one is a
// holder of the duplicate-role issue and each lands in a seat no post row holds yet.
const PROMOTED = [
  "Councillor 09 Scale",
  "Councillor 18 Scale",
  "Councillor 21 Scale",
  "Councillor 30 Scale",
  "Councillor 33 Scale",
];

test.describe("Review card at scale", () => {
  test("carries anchored and person-level issues at density", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${SCALE_CHANGESET_ID}`);

    // A field-anchored issue on every holder of a role marked unique — the case the collapse
    // rule's rule 2 exists for. In the editor the issue renders under the field it anchors to,
    // which is Post: the seat is what a reviewer would change to resolve it.
    // One editor at a time now that the modal is the only one: the count this used to make
    // across five on-screen editors is the loop.
    // Filtered on the duplicate issue's own wording, not on the role name: each of these five
    // also carries a `moved_person` issue naming the same role, so "council president" matches
    // twice per holder.
    for (const name of PROMOTED) {
      await openEditorFor(page, name);
      const editor = editorFor(page, name);
      await expect(
        editor.locator(".person-editor__issue").filter({ hasText: "marked as unique" }),
      ).toHaveCount(1);
      await expect(
        editor.locator(".person-editor__field").filter({ hasText: "Post" }),
      ).toHaveCount(1);
      await page.keyboard.press("Escape");
    }
  });

  test("offers the projected post, and says it does not exist yet", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(`/review/session?changeset_id=${SCALE_CHANGESET_ID}`);
    await openEditorFor(page, "Councillor 09 Scale");

    // Ingest mints no posts, so a promotion names a post no row holds. The picker has to offer
    // it anyway — otherwise the derivation's answer is simply missing and the field reads as
    // unanswered — and has to say that accepting it creates the post.
    const picker = editorFor(page, "Councillor 09 Scale").locator(
      ".field-control__office",
    );
    await expect(picker.locator("option[selected], option:checked")).toContainText(
      "new post",
    );
  });
});
