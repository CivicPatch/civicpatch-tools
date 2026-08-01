import { describe, it, expect } from "vitest";
import {
  openPullRequests,
  peopleEditBlockers,
  jurisdictionEditBlockers,
  editingBlockedReason,
  jurisdictionEditBlockedReason,
  REQUEST_TYPE,
  type HistoryEntry,
} from "../pages/jurisdictions-page/open-pull-requests.ts";

const entry = (overrides: Partial<HistoryEntry> = {}): HistoryEntry => ({
  request_id: "req-1",
  created_at: "2026-07-12T00:00:00Z",
  pull_request_url: "https://github.com/CivicPatch/open-data/pull/4821",
  pull_request_status: "open",
  request_type: REQUEST_TYPE.PEOPLE,
  ...overrides,
});

describe("openPullRequests", () => {
  it("keeps only entries whose PR is open", () => {
    const history = [
      entry({ request_id: "a" }),
      entry({ request_id: "b", pull_request_status: "merged" }),
      entry({ request_id: "c", pull_request_status: "closed" }),
      // A run that never produced a PR at all.
      entry({ request_id: "d", pull_request_status: null, pull_request_url: null }),
    ];
    expect(openPullRequests(history).map((e) => e.request_id)).toEqual(["a"]);
  });

  it("is empty for empty history", () => {
    expect(openPullRequests([])).toEqual([]);
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
    expect(editingBlockedReason([entry({ pull_request_url: null })])).toBe(
      "A pull request is awaiting review. Publish or close it before editing directly.",
    );
  });

  it("counts rather than naming when several are open", () => {
    expect(editingBlockedReason([entry(), entry({ request_id: "b" })])).toBe(
      "2 pull requests are awaiting review. Publish or close them before editing directly.",
    );
  });
});


// The two kinds edit different files, so each only blocks a second edit to its own.
// Crossing them would mean saving a website url locked you out of the roster, or a
// pending scrape locked the website field it never touches.
describe("edit blockers", () => {
  const open = [
    entry({ request_id: "scrape" }),
    entry({ request_id: "edit", request_type: REQUEST_TYPE.JURISDICTION_MANUAL_EDIT }),
  ];

  it("blocks people edits on scrapes only", () => {
    expect(peopleEditBlockers(open).map((e) => e.request_id)).toEqual(["scrape"]);
  });

  it("blocks jurisdiction edits on manual edits only", () => {
    expect(jurisdictionEditBlockers(open).map((e) => e.request_id)).toEqual(["edit"]);
  });

  it("treats an unknown type as a people blocker, which is the safe default", () => {
    expect(peopleEditBlockers([entry({ request_type: null })])).toHaveLength(1);
    expect(jurisdictionEditBlockers([entry({ request_type: null })])).toHaveLength(0);
  });
});


// Jurisdiction edits auto-merge, so one still open means the merge failed. The block
// exists because a second edit branches from main — which lacks the stuck change —
// so publishing it would silently drop the first.
describe("jurisdictionEditBlockedReason", () => {
  const stuck = (overrides = {}) =>
    entry({ request_type: REQUEST_TYPE.JURISDICTION_MANUAL_EDIT, ...overrides });

  it("is null when nothing is stuck", () => {
    expect(jurisdictionEditBlockedReason([])).toBeNull();
  });

  it("names the stuck edit and says it did not auto-merge", () => {
    expect(jurisdictionEditBlockedReason([stuck()])).toBe(
      "Edit #4821 did not auto-merge. Resolve or close it before editing again.",
    );
  });

  it("counts when several are stuck", () => {
    expect(jurisdictionEditBlockedReason([stuck(), stuck({ request_id: "b" })])).toBe(
      "2 edits did not auto-merge. Resolve or close them before editing again.",
    );
  });
});
