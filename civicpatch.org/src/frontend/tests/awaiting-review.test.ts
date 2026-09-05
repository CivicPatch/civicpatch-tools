import { describe, it, expect } from "vitest";
import {
  pendingReviews,
  peopleEditBlockers,
  jurisdictionEditBlockers,
  editingBlockedReason,
  jurisdictionEditBlockedReason,
  CHANGESET_KIND,
  type InFlightEntry,
} from "../pages/jurisdictions-page/awaiting-review.ts";

const entry = (overrides: Partial<InFlightEntry> = {}): InFlightEntry => ({
  id: "req-1",
  created_at: "2026-07-12T00:00:00Z",
  change_url: "https://github.com/CivicPatch/open-data/pull/4821",
  review_status: "pending",
  kind: CHANGESET_KIND.SCRAPE,
  ...overrides,
});

describe("pendingReviews", () => {
  // The server decides, via `AVAILABLE_FOR_REVIEW` — the same predicate the queue and the
  // review session select on. These pin that the page takes that answer rather than
  // reconstructing one from `review_status`, which is what drifted.
  it("keeps what the pool says it holds", () => {
    const history = [
      entry({ id: "a", awaiting_review: true }),
      entry({ id: "b", review_status: "published", awaiting_review: false }),
      entry({ id: "c", review_status: "dismissed", awaiting_review: false }),
    ];
    expect(pendingReviews(history).map((e) => e.id)).toEqual(["a"]);
  });

  it("drops a scrape that is still running, though it reads as pending", () => {
    // `pending` is true from the moment a request exists, so deriving from it offered a Review
    // button for a roster the scrape had not produced. The pool excludes it: no `data_json`.
    const history = [
      entry({ id: "done", awaiting_review: true }),
      entry({
        id: "running",
        review_status: "pending",
        is_running: true,
        awaiting_review: false,
      }),
    ];
    expect(pendingReviews(history).map((e) => e.id)).toEqual(["done"]);
  });

  it("is empty for empty history", () => {
    expect(pendingReviews([])).toEqual([]);
  });
});

describe("editingBlockedReason", () => {
  // The guard exists because both paths write the same open-data file; editing
  // under an open PR would open a second one against the same content.
  it("is null when nothing is open, so editing stays available", () => {
    expect(editingBlockedReason([])).toBeNull();
  });

  it("names the pull request, so the disabled roster is not a dead end", () => {
    expect(editingBlockedReason([entry()])).toBe(
      "Pull request #4821 is awaiting review. Publish or close it before editing directly.",
    );
  });

  it("falls back to an unnumbered phrasing when history has no PR url", () => {
    expect(editingBlockedReason([entry({ change_url: null })])).toBe(
      "A pull request is awaiting review. Publish or close it before editing directly.",
    );
  });

  it("counts rather than naming when several are open", () => {
    expect(editingBlockedReason([entry(), entry({ id: "b" })])).toBe(
      "2 pull requests are awaiting review. Publish or close them before editing directly.",
    );
  });
});


// The two kinds edit different files, so each only blocks a second edit to its own.
// Crossing them would mean saving a website url locked you out of the roster, or a
// pending scrape locked the website field it never touches.
describe("edit blockers", () => {
  const open = [
    entry({ id: "scrape" }),
    entry({ id: "edit", kind: CHANGESET_KIND.JURISDICTION_EDIT }),
  ];

  it("blocks people edits on scrapes only", () => {
    expect(peopleEditBlockers(open).map((e) => e.id)).toEqual(["scrape"]);
  });

  it("blocks jurisdiction edits on manual edits only", () => {
    expect(jurisdictionEditBlockers(open).map((e) => e.id)).toEqual(["edit"]);
  });

  it("treats an unknown type as a people blocker, which is the safe default", () => {
    expect(peopleEditBlockers([entry({ kind: null })])).toHaveLength(1);
    expect(jurisdictionEditBlockers([entry({ kind: null })])).toHaveLength(0);
  });
});


// Jurisdiction edits auto-merge, so one still open means the merge failed. The block
// exists because a second edit branches from main — which lacks the stuck change —
// so publishing it would silently drop the first.
describe("jurisdictionEditBlockedReason", () => {
  const stuck = (overrides = {}) =>
    entry({ kind: CHANGESET_KIND.JURISDICTION_EDIT, ...overrides });

  it("is null when nothing is stuck", () => {
    expect(jurisdictionEditBlockedReason([])).toBeNull();
  });

  it("names the stuck edit and says it did not auto-merge", () => {
    expect(jurisdictionEditBlockedReason([stuck()])).toBe(
      "Edit #4821 did not auto-merge. Resolve or close it before editing again.",
    );
  });

  it("counts when several are stuck", () => {
    expect(jurisdictionEditBlockedReason([stuck(), stuck({ id: "b" })])).toBe(
      "2 edits did not auto-merge. Resolve or close them before editing again.",
    );
  });
});

