/**
 * User story: dropping a person from a card
 *
 * Given I am reviewing a re-scrape
 * When I delete a person the database already holds
 * Then their card reads as departing, they are counted under Removed
 * And publishing omits them, which the backend reads as a deletion
 * But Undo brings them back, and publishing carries them again
 *
 * And when I delete a person this scrape *added*, their card goes away
 * entirely — they were never in the database, so there is nothing to drop.
 *
 * Deletion is held beside the people list (usePeopleState's deletedIds), not as
 * a field on the record, so nothing about it is visible in the patch except the
 * person's absence. That absence is what these tests assert. The merge itself is
 * stubbed — as in review-publish-wiring — so this covers the client wiring.
 */

import { test, expect } from "../fixtures/index.js";
import { RECONCILE_REQUEST_ID } from "../fixtures/db.js";

const MERGE_ENDPOINT = "**/api/v1/pull_requests/*/save-and-merge";
const MERGE_STATUS_ENDPOINT = "**/api/v1/pull_requests/*/merge-status";

async function stubMerge(page) {
  await page.route(MERGE_STATUS_ENDPOINT, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "merged" }),
    }),
  );
  const captured = { body: null };
  await page.route(MERGE_ENDPOINT, async (route) => {
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
  await page.goto(`/review/session?request_id=${RECONCILE_REQUEST_ID}`);
  await expect(page.locator("people-diff")).toBeVisible();
}

// Match on the card's own name header — a name can also appear inside another
// card's "Link to person" picker, which hasText would happily match.
const personCard = (page, name) =>
  page
    .locator(".people-diff__person")
    .filter({ has: page.locator(".people-diff__name", { hasText: name }) });

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
    await expect(maria).toHaveClass(/people-diff__person--changed/);
    await expect(personCard(page, "Bob Clerk").locator(".people-diff__delete")).toHaveCount(0);

    await maria.locator(".people-diff__delete").click();

    // The card stays in place as a departing ghost, and Delete gives way to Undo.
    await expect(maria).toHaveClass(/people-diff__person--deleted/);
    await expect(maria.locator(".people-diff__undo")).toBeVisible();
    await expect(maria.locator(".people-diff__delete")).toHaveCount(0);

    // Deleting is an edit, so the card publishes under the dirty label.
    const publishBtn = page.locator(".review-page__merge-btn");
    await expect(publishBtn).toHaveText(/Save and Publish/);
    await publishBtn.click();

    await expect.poll(() => merge.body).not.toBeNull();
    // Tom survives; Maria's absence is the deletion.
    expect(publishedIds(merge.body)).toEqual(["recon-tom"]);
  });

  test("Undo restores a deleted person, and publishing carries them again", async ({
    authenticatedPage: page,
  }) => {
    const merge = await stubMerge(page);
    await openReconcileCard(page);

    const maria = personCard(page, "Maria González");
    await maria.locator(".people-diff__delete").click();
    await expect(maria).toHaveClass(/people-diff__person--deleted/);

    await maria.locator(".people-diff__undo").click();
    await expect(maria).toHaveClass(/people-diff__person--changed/);
    await expect(maria.locator(".people-diff__delete")).toBeVisible();

    // Undo returns the card to its loaded state, so there is nothing to patch:
    // publishing sends no people at all and the button drops the dirty label.
    // That is a stronger check than Maria reappearing in a payload — it proves
    // the deletion left no residue anywhere in the state.
    const publishBtn = page.locator(".review-page__merge-btn");
    await expect(publishBtn).not.toHaveText(/Save and Publish/);
    await publishBtn.click();

    await expect.poll(() => merge.body).not.toBeNull();
    // saveAndEnqueueMerge omits `data` entirely when there is no patch, rather
    // than sending null — so an absent key is what "nothing to publish" is.
    expect(merge.body.data).toBeUndefined();
  });

  test("a deleted person is counted under Removed, not Unchanged", async ({
    authenticatedPage: page,
  }) => {
    await openReconcileCard(page);

    const removedChip = page.locator(".people-diff__chip--removed .people-diff__chip-count");
    // Bob alone to start: the scrape didn't find him.
    await expect(removedChip).toHaveText("1");

    await personCard(page, "Maria González").locator(".people-diff__delete").click();

    // Maria joins him. Before deletions were folded into the diff, she stayed
    // classified by her fields and never reached this chip.
    await expect(removedChip).toHaveText("2");
    await page.locator(".people-diff__chip--removed").click();
    await expect(personCard(page, "Maria González")).toBeVisible();
  });

  test("a person you are dropping is not offered as a link target", async ({
    authenticatedPage: page,
  }) => {
    await openReconcileCard(page);

    // Tom is the unmatched ADDED card, so he carries the link picker. Bob is the
    // only person the scrape didn't find, so he is the only candidate — one
    // option plus the "Link to person…" placeholder.
    const linkOptions = personCard(page, "Tom Treasurer").locator(".people-diff__link option");
    await expect(linkOptions).toHaveCount(2);
    await expect(linkOptions).toContainText(["Link to person", "Bob Clerk"]);

    await personCard(page, "Maria González").locator(".people-diff__delete").click();

    // foldDeletions types a deleted person REMOVED, which is what candidates are
    // drawn from — so without the exclusion Maria would appear here. Linking
    // adopts the target's id, so picking her would hand Tom an id already in
    // deletedIds and drop him from the publish payload without saying so.
    await expect(linkOptions).toHaveCount(2);
    await expect(linkOptions).not.toContainText(["María", "Maria González"]);
  });

  test("deleting an added person removes their card entirely", async ({
    authenticatedPage: page,
  }) => {
    const merge = await stubMerge(page);
    await openReconcileCard(page);

    const tom = personCard(page, "Tom Treasurer");
    await expect(tom).toHaveClass(/people-diff__person--added/);
    await tom.locator(".people-diff__delete").click();

    // Added-then-deleted is a net no-op — there is no database record to drop,
    // so the card has nothing left to say.
    await expect(personCard(page, "Tom Treasurer")).toHaveCount(0);

    await page.locator(".review-page__merge-btn").click();
    await expect.poll(() => merge.body).not.toBeNull();
    expect(publishedIds(merge.body)).not.toContain("recon-tom");
  });
});
