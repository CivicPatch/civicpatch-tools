import { describe, it, expect } from "vitest";
import {
  openPullRequests,
  editingBlockedReason,
  type HistoryEntry,
} from "../pages/jurisdictions-page/open-pull-requests.ts";

const entry = (overrides: Partial<HistoryEntry> = {}): HistoryEntry => ({
  request_id: "req-1",
  created_at: "2026-07-12T00:00:00Z",
  pull_request_url: "https://github.com/CivicPatch/open-data/pull/4821",
  pull_request_status: "open",
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
