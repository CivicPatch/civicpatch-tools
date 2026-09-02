/**
 * User story: dropping a person from a card
 *
 * Given I am reviewing a re-scrape
 * When I delete a person the database already holds
 * Then their card reads as departing, they are counted under Removed
 * And publishing omits them, which the backend reads as a deletion
 * But Undo brings them back, and publishing carries them again
 *
 * And when I delete a person this scrape *added*, their card stays and reads as
 * departing too — the removal is undoable, and their absence from the payload
 * is the whole of it, since there was never a database record to drop.
 *
 * Deletion is held beside the people list (usePeopleState's deletedIds), not as
 * a field on the record, so nothing about it is visible in the patch except the
 * person's absence. That absence is what these tests assert. The merge itself is
 * stubbed — as in review-publish-wiring — so this covers the client wiring.
 */

import { test, expect } from "../fixtures/index.js";
import { personUuid, RECONCILE_CHANGESET_ID } from "../fixtures/db.js";
import { openDetail, openOverview, editorFor, rowFor } from "./helpers/review-card.js";

const APPROVE_ENDPOINT = "**/api/v1/reviews/*/publish";


async function stubMerge(page) {
  await page.route(APPROVE_ENDPOINT, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "merged" }),
    }),
  );
  const captured = { body: null };
  await page.route(APPROVE_ENDPOINT, async (route) => {
    captured.body = route.request().postDataJSON();
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ status: "enqueued" }),
    });
  });
  return captured;
}

async function openReconcileCard(page) {
  await page.goto(`/review/session?changeset_id=${RECONCILE_CHANGESET_ID}`);
  await openDetail(page);
}

const personCard = editorFor;

const publishedIds = (body) =>
  (body.data ?? []).map((entry) => entry.id);

test.describe("Delete a person", () => {
  test("a deleted existing person is dropped from the published payload", async ({
    authenticatedPage: page,
  }) => {
    const merge = await stubMerge(page);
    await openReconcileCard(page);

    // Maria pairs as CHANGED, so she has a Delete button; Bob is REMOVED
    // (no new-side record) and must not offer one.
    const maria = personCard(page, "Maria González");
    await expect(maria).toHaveClass(/person-editor--changed/);
    await expect(personCard(page, "Bob Clerk").locator(".person-editor__delete")).toHaveCount(0);

    await maria.locator(".person-editor__delete").click();

    // The card stays in place as a departing ghost, and Delete gives way to Undo.
    await expect(maria).toHaveClass(/person-editor--deleted/);
    await expect(maria.locator(".person-editor__restore-person")).toBeVisible();
    await expect(maria.locator(".person-editor__delete")).toHaveCount(0);

    // Deleting is an edit, so the card publishes under the dirty label.
    const approveBtn = page.locator(".review-page__approve-btn");
    await expect(approveBtn).toHaveText(/Save and approve/);
    await approveBtn.click();

    await expect.poll(() => merge.body).not.toBeNull();
    // Tom survives; Maria's absence is the deletion.
    // Ids are uuids since migration 144; the fixture hashes its slug, so name it the same way.
    expect(publishedIds(merge.body)).toEqual([personUuid("recon-tom")]);
  });

  test("Undo restores a deleted person, and publishing carries them again", async ({
    authenticatedPage: page,
  }) => {
    const merge = await stubMerge(page);
    await openReconcileCard(page);

    const maria = personCard(page, "Maria González");
    await maria.locator(".person-editor__delete").click();
    await expect(maria).toHaveClass(/person-editor--deleted/);

    await maria.locator(".person-editor__restore-person").click();
    await expect(maria).toHaveClass(/person-editor--changed/);
    await expect(maria.locator(".person-editor__delete")).toBeVisible();

    // Undo returns the card to its loaded state, so there is nothing to patch:
    // publishing sends no people at all and the button drops the dirty label.
    // That is a stronger check than Maria reappearing in a payload — it proves
    // the deletion left no residue anywhere in the state.
    const approveBtn = page.locator(".review-page__approve-btn");
    await expect(approveBtn).not.toHaveText(/Save and approve/);
    await approveBtn.click();

    await expect.poll(() => merge.body).not.toBeNull();
    // saveAndEnqueueMerge omits `data` entirely when there is no patch, rather
    // than sending null — so an absent key is what "nothing to publish" is.
    expect(merge.body.data).toBeUndefined();
  });

  test("a deleted person is classified as departing, not unchanged", async ({
    authenticatedPage: page,
  }) => {
    await openReconcileCard(page);
    await personCard(page, "Maria González").locator(".person-editor__delete").click();

    // The editor has no filter chips — the collapse rule replaced them — so the
    // classification is asserted where it is now visible: her card reads as a
    // departure, and Overview files her under To review rather than in the
    // Unchanged face strip. Before deletions were folded into the diff she stayed
    // classified by her fields and landed in the faded group.
    await expect(personCard(page, "Maria González")).toHaveClass(/person-editor--deleted/);

    await openOverview(page);
    await expect(rowFor(page, "Maria González")).toHaveClass(/review-row--deleted/);
    await expect(
      page.locator(".review-overview__strip").getByText("Maria González"),
    ).toHaveCount(0);
  });

  test("a person you are removing is not offered as a merge candidate", async ({
    authenticatedPage: page,
  }) => {
    await openReconcileCard(page);

    // "Are these two the same person" is a question about any pair, so everyone
    // else on the card starts out a candidate — not just the ones the scrape
    // failed to find.
    const tom = personCard(page, "Tom Treasurer");
    await tom.locator(".person-editor__merge").click();
    const faces = tom.locator(".person-editor__merge-faces .review-face");
    const faceFor = (name) => faces.filter({ hasText: name });

    await expect(faces).toHaveCount(2);
    await expect(faceFor("Maria González")).toHaveCount(1);
    await expect(faceFor("Bob Clerk")).toHaveCount(1);

    await personCard(page, "Maria González").locator(".person-editor__delete").click();

    // "Drop this person" and "keep parts of this person" are contradictory
    // answers to the same question, so removing her withdraws her from the pool.
    // Merging adopts the survivor's id, so offering her risks handing Tom an id
    // already in removedIds and dropping him from the payload without saying so.
    await expect(faces).toHaveCount(1);
    await expect(faceFor("Maria González")).toHaveCount(0);
  });

  test("deleting an added person keeps an undoable card, but drops them from the payload", async ({
    authenticatedPage: page,
  }) => {
    const merge = await stubMerge(page);
    await openReconcileCard(page);

    const tom = personCard(page, "Tom Treasurer");
    await expect(tom).toHaveClass(/person-editor--added/);
    await tom.locator(".person-editor__delete").click();

    // Added-then-deleted is a net no-op in the payload, but the row is still in
    // the list and the removal is undoable, so the card stays as a ghost.
    await expect(tom).toHaveClass(/person-editor--deleted/);
    await expect(tom.locator(".person-editor__restore-person")).toBeVisible();

    await page.locator(".review-page__approve-btn").click();
    await expect.poll(() => merge.body).not.toBeNull();
    expect(publishedIds(merge.body)).not.toContain(personUuid("recon-tom"));
  });
});
