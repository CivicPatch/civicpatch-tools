import { describe, it, expect, vi } from "vitest";
import {
  boot,
  goToEntry,
  endSessionAndExit,
  mergeCurrent,
  saveCurrent,
  closeCurrent,
  buildEntry,
  type Effects,
  type ReviewApi,
} from "../pages/review-session-page/review-actions.ts";
import { ActionType, type CurrentEntry } from "../pages/review-session-page/review-state.ts";
import { landingUrl } from "../pages/review-routes.ts";

const STATE = "nj";

function fakeApi(overrides: Partial<ReviewApi> = {}): ReviewApi {
  return {
    fetchActiveReviewSession: vi.fn(async () => ({ data: null })),
    navigateToEntry: vi.fn(async () => ({ data: null })),
    fetchReview: vi.fn(async () => ({ data: { issues: [] } })),
    endReviewSession: vi.fn(async () => ({ data: null })),
    fetchPullRequestByRequestId: vi.fn(async () => ({ data: null })),
    saveReviewData: vi.fn(async () => ({ status: "saved" })),
    ...overrides,
  };
}

function fakeEffects(api: ReviewApi): Effects {
  return {
    api,
    dispatch: vi.fn(),
    navigate: vi.fn(),
    setRequestIdParam: vi.fn(),
    trackMerge: vi.fn(async () => ({ ok: true })),
    trackClose: vi.fn(),
  };
}

function cardData(overrides = {}) {
  return {
    request_id: "req-1",
    entry_number: 2,
    total: 5,
    has_next: true,
    jurisdiction: { ocdid: "ocd-x", name: "X City", path: null },
    pr: { url: "u", status: "open", reviewState: null, number: 123 },
    existing: [],
    proposed: [],
    sources: [],
    ...overrides,
  };
}

function activeSession(overrides = {}) {
  return {
    session_id: "s1",
    daily_goal: 10,
    current_entry_number: 2,
    resolved_entry_numbers: [1],
    session_request_ids: ["req-1"],
    ...overrides,
  };
}

const lastAction = (e: Effects) => (e.dispatch as any).mock.calls.at(-1)[0];
const dispatchedTypes = (e: Effects) => (e.dispatch as any).mock.calls.map((c: any[]) => c[0].type);

describe("boot", () => {
  it("resumes an active session at its current entry when no PR is in the URL", async () => {
    const api = fakeApi({
      fetchActiveReviewSession: vi.fn(async () => ({ data: activeSession() })),
      navigateToEntry: vi.fn(async () => ({ data: cardData() })),
    });
    const e = fakeEffects(api);
    await boot(STATE, null, null, e);

    expect(api.navigateToEntry).toHaveBeenCalledWith("s1", 2);
    expect(e.navigate).not.toHaveBeenCalled();
    const action = lastAction(e);
    expect(action.type).toBe(ActionType.SESSION_LOADED);
    expect(action.payload.session).toEqual({ id: "s1", daily_goal: 10 });
    expect(action.payload.entry_number).toBe(2);
    expect(action.payload.total).toBe(5);
    expect(e.setRequestIdParam).toHaveBeenCalledWith("req-1");
  });

  it("stays in session mode for a deeplink to one of the session's own PRs (refresh)", async () => {
    const api = fakeApi({
      fetchActiveReviewSession: vi.fn(async () => ({ data: activeSession() })),
      navigateToEntry: vi.fn(async () => ({ data: cardData() })),
    });
    const e = fakeEffects(api);
    await boot(STATE, "req-1", null, e);

    expect(api.fetchPullRequestByRequestId).not.toHaveBeenCalled();
    expect(lastAction(e).payload.session).toEqual({ id: "s1", daily_goal: 10 });
  });

  // The jurisdiction page's Review button links with pull_request, which names one
  // card outright. Answering it with wherever the session was parked would land the
  // reviewer on a different town — the reason this param is distinct from request_id.
  it("opens the named pull request standalone, even mid-session", async () => {
    const api = fakeApi({
      fetchActiveReviewSession: vi.fn(async () => ({
        data: activeSession({ session_request_ids: ["req-1", "req-7"] }),
      })),
      navigateToEntry: vi.fn(async () => ({ data: cardData({ request_id: "req-1" }) })),
      fetchPullRequestByRequestId: vi.fn(async () => ({
        data: cardData({ request_id: "req-7", entry_number: 1, has_next: false }),
      })),
    });
    const e = fakeEffects(api);
    await boot(STATE, "req-1", "req-7", e);

    expect(api.fetchPullRequestByRequestId).toHaveBeenCalledWith("req-7");
    expect(lastAction(e).payload.current_entry.request_id).toBe("req-7");
    expect(lastAction(e).payload.session).toBeNull();
    // The session is beside the point for a link in from outside — not even looked up.
    expect(api.fetchActiveReviewSession).not.toHaveBeenCalled();
    expect(api.navigateToEntry).not.toHaveBeenCalled();
  });

  it("shows a standalone PR when the deeplink is not part of the active session", async () => {
    const api = fakeApi({
      fetchActiveReviewSession: vi.fn(async () => ({ data: activeSession() })),
      fetchPullRequestByRequestId: vi.fn(async () => ({ data: cardData({ entry_number: 1, has_next: false }) })),
    });
    const e = fakeEffects(api);
    await boot(STATE, "req-999", null, e);

    expect(api.fetchPullRequestByRequestId).toHaveBeenCalledWith("req-999");
    expect(lastAction(e).payload.session).toBeNull();
  });

  it("shows a standalone PR when there is no active session", async () => {
    const api = fakeApi({
      fetchPullRequestByRequestId: vi.fn(async () => ({ data: cardData({ entry_number: 1, has_next: false }) })),
    });
    const e = fakeEffects(api);
    await boot(STATE, "req-999", null, e);

    expect(lastAction(e).payload.session).toBeNull();
    expect(e.navigate).not.toHaveBeenCalled();
  });

  it("navigates to the landing when there is no session and no PR", async () => {
    const e = fakeEffects(fakeApi());
    await boot(STATE, null, null, e);
    expect(e.navigate).toHaveBeenCalledWith(landingUrl(STATE));
    expect(e.dispatch).not.toHaveBeenCalled();
  });

  it("falls back to the landing when a standalone deeplink PR is stale (404)", async () => {
    const api = fakeApi({ fetchPullRequestByRequestId: vi.fn(async () => { throw new Error("HTTP 404"); }) });
    const e = fakeEffects(api);
    await boot(STATE, "req-stale", null, e);
    expect(e.navigate).toHaveBeenCalledWith(landingUrl(STATE));
    expect(e.dispatch).not.toHaveBeenCalled();
  });

  it("reports an error to the reducer when a fetch throws", async () => {
    const api = fakeApi({ fetchActiveReviewSession: vi.fn(async () => { throw new Error("HTTP 500"); }) });
    const e = fakeEffects(api);
    await boot(STATE, null, null, e);
    const action = lastAction(e);
    expect(action.type).toBe(ActionType.LOAD_FAILED);
    expect(action.payload.message).toBe("HTTP 500");
  });
});

describe("goToEntry", () => {
  it("marks nav started, loads the entry, and reflects the PR into the URL", async () => {
    const api = fakeApi({ navigateToEntry: vi.fn(async () => ({ data: cardData({ entry_number: 3 }) })) });
    const e = fakeEffects(api);
    await goToEntry("s1", 3, STATE, e);

    expect(dispatchedTypes(e)).toEqual([ActionType.NAV_STARTED, ActionType.ENTRY_LOADED]);
    expect(api.navigateToEntry).toHaveBeenCalledWith("s1", 3);
    expect(lastAction(e).payload.total).toBe(5);
    expect(e.setRequestIdParam).toHaveBeenCalledWith("req-1");
  });

  it("ends the session and exits when navigation returns no data", async () => {
    const api = fakeApi({ navigateToEntry: vi.fn(async () => ({ data: null })) });
    const e = fakeEffects(api);
    await goToEntry("s1", 99, STATE, e);

    expect(api.endReviewSession).toHaveBeenCalledWith("s1");
    expect(e.navigate).toHaveBeenCalledWith(landingUrl(STATE));
  });
});

describe("endSessionAndExit", () => {
  it("ends the session then navigates to the landing", async () => {
    const e = fakeEffects(fakeApi());
    await endSessionAndExit("s1", STATE, e);
    expect(e.api.endReviewSession).toHaveBeenCalledWith("s1");
    expect(e.navigate).toHaveBeenCalledWith(landingUrl(STATE));
  });

  it("just navigates when there is no session (deeplink Exit)", async () => {
    const e = fakeEffects(fakeApi());
    await endSessionAndExit(null, STATE, e);
    expect(e.api.endReviewSession).not.toHaveBeenCalled();
    expect(e.navigate).toHaveBeenCalledWith(landingUrl(STATE));
  });
});

const current: CurrentEntry = {
  request_id: "req-1",
  jurisdiction: { ocdid: "ocd-x", name: "X City", path: null },
  pr: { url: "u", status: "open", reviewState: null, number: 123 },
  pr_people: { existing: [], proposed: [] },
  review_data: null,
  source_content_urls: [],
  is_read_only: false,
  has_next: true,
};

// A deeplinked PR has no session behind it (loadFirstEntry passes session: null).
// The actions still work — they key off the PR, not the session — but there is no
// queue to advance into, so a terminal action returns to the jurisdiction page.
describe("standalone deeplink (no session)", () => {
  const standalone: CurrentEntry = {
    ...current,
    jurisdiction: {
      ocdid: "ocd-jurisdiction/country:us/state:me/county:cumberland/place:windham/government",
      name: "Windham town",
      path: null,
    },
  };
  const jurisdictionPage = "/me/local/county_cumberland__place_windham";

  it("publishes, then returns to the jurisdiction page instead of advancing", async () => {
    const api = fakeApi();
    const e = fakeEffects(api);
    await mergeCurrent(standalone, null, 1, [{ id: "p1" }], STATE, e);

    expect(e.trackMerge).toHaveBeenCalled();
    expect(dispatchedTypes(e)).toContain(ActionType.MARK_RESOLVED);
    // The bug this replaces: navigateToEntry("") POSTs to /review-sessions//navigate,
    // which 405s, so a publish that already succeeded surfaced as LOAD_FAILED.
    expect(api.navigateToEntry).not.toHaveBeenCalled();
    expect(dispatchedTypes(e)).not.toContain(ActionType.LOAD_FAILED);
    expect(e.navigate).toHaveBeenCalledWith(jurisdictionPage);
  });

  it("closes, then returns to the jurisdiction page", async () => {
    const api = fakeApi();
    const e = fakeEffects(api);
    await closeCurrent(standalone, null, 1, STATE, e);

    expect(e.trackClose).toHaveBeenCalled();
    expect(api.navigateToEntry).not.toHaveBeenCalled();
    expect(e.navigate).toHaveBeenCalledWith(jurisdictionPage);
  });

  it("saves and stays put — the PR is still open and still being edited", async () => {
    const api = fakeApi();
    const e = fakeEffects(api);
    await saveCurrent(standalone, null, 1, [{ id: "p1" }], STATE, e);

    expect(api.saveReviewData).toHaveBeenCalled();
    expect(dispatchedTypes(e)).toContain(ActionType.MARK_SAVED);
    expect(api.navigateToEntry).not.toHaveBeenCalled();
    expect(e.navigate).not.toHaveBeenCalled();
  });

  it("still reports a rejected publish rather than navigating away", async () => {
    const api = fakeApi();
    const e = fakeEffects(api);
    (e.trackMerge as any).mockResolvedValue({ ok: false, error: "phones: Invalid phone number" });
    await mergeCurrent(standalone, null, 1, [{ id: "p1" }], STATE, e);

    expect(dispatchedTypes(e)).toContain(ActionType.MARK_FAILED);
    expect(e.navigate).not.toHaveBeenCalled();
  });
});

describe("mergeCurrent", () => {
  it("publishes the merge, marks the entry resolved, and advances", async () => {
    const api = fakeApi({ navigateToEntry: vi.fn(async () => ({ data: cardData({ entry_number: 3 }) })) });
    const e = fakeEffects(api);
    const people = [{ id: "p1" }];
    await mergeCurrent(current, "s1", 2, people, STATE, e);

    expect(e.trackMerge).toHaveBeenCalledWith("req-1", "ocd-x", people, "X City");
    expect(dispatchedTypes(e)).toContain(ActionType.MARK_RESOLVED);
    expect(api.navigateToEntry).toHaveBeenCalledWith("s1", 3);
  });

  it("flags the entry failed and stays put when the publish is rejected", async () => {
    const api = fakeApi({ navigateToEntry: vi.fn(async () => ({ data: cardData({ entry_number: 3 }) })) });
    const e = fakeEffects(api);
    (e.trackMerge as any).mockResolvedValue({ ok: false, error: "phones: Invalid phone number" });
    await mergeCurrent(current, "s1", 2, [{ id: "p1" }], STATE, e);

    expect(e.dispatch).toHaveBeenCalledWith({
      type: ActionType.MARK_FAILED,
      payload: { entry_number: 2, message: "phones: Invalid phone number" },
    });
    expect(dispatchedTypes(e)).not.toContain(ActionType.MARK_RESOLVED);
    expect(api.navigateToEntry).not.toHaveBeenCalled();
  });

  it("publishes a scrape that has no pull request", async () => {
    const api = fakeApi({ navigateToEntry: vi.fn(async () => ({ data: cardData({ entry_number: 3 }) })) });
    const e = fakeEffects(api);
    await mergeCurrent({ ...current, pr: undefined } as any, "s1", 2, null, STATE, e);
    expect(e.trackMerge).toHaveBeenCalledWith("req-1", "ocd-x", null, "X City");
  });

  it("does nothing without a request id", async () => {
    const e = fakeEffects(fakeApi());
    await mergeCurrent({ ...current, request_id: null } as any, "s1", 2, null, STATE, e);
    expect(e.trackMerge).not.toHaveBeenCalled();
    expect(e.dispatch).not.toHaveBeenCalled();
  });
});

describe("saveCurrent", () => {
  it("commits the edits, marks the entry saved, and advances", async () => {
    const api = fakeApi({ navigateToEntry: vi.fn(async () => ({ data: cardData({ entry_number: 3 }) })) });
    const e = fakeEffects(api);
    const people = [{ id: "p1" }];
    await saveCurrent(current, "s1", 2, people, STATE, e);

    expect(api.saveReviewData).toHaveBeenCalledWith("req-1", "ocd-x", people);
    expect(dispatchedTypes(e)).toContain(ActionType.MARK_SAVED);
    expect(api.navigateToEntry).toHaveBeenCalledWith("s1", 3);
  });

  it("does not credit the entry as resolved", async () => {
    const api = fakeApi({ navigateToEntry: vi.fn(async () => ({ data: cardData({ entry_number: 3 }) })) });
    const e = fakeEffects(api);
    await saveCurrent(current, "s1", 2, [{ id: "p1" }], STATE, e);
    expect(dispatchedTypes(e)).not.toContain(ActionType.MARK_RESOLVED);
  });

  it("flags the entry failed and stays put when the save is rejected", async () => {
    const api = fakeApi({
      navigateToEntry: vi.fn(async () => ({ data: cardData({ entry_number: 3 }) })),
      saveReviewData: vi.fn(async () => { throw new Error("phones: Invalid phone number"); }),
    });
    const e = fakeEffects(api);
    await saveCurrent(current, "s1", 2, [{ id: "p1" }], STATE, e);

    expect(e.dispatch).toHaveBeenCalledWith({
      type: ActionType.MARK_FAILED,
      payload: { entry_number: 2, message: "phones: Invalid phone number" },
    });
    expect(dispatchedTypes(e)).not.toContain(ActionType.MARK_SAVED);
    expect(api.navigateToEntry).not.toHaveBeenCalled();
  });

  it("saves a scrape that has no pull request", async () => {
    const api = fakeApi({ navigateToEntry: vi.fn(async () => ({ data: cardData({ entry_number: 3 }) })) });
    const e = fakeEffects(api);
    await saveCurrent({ ...current, pr: undefined } as any, "s1", 2, [{ id: "p1" }], STATE, e);
    expect(e.api.saveReviewData).toHaveBeenCalled();
  });

  it("does nothing without a request id", async () => {
    const e = fakeEffects(fakeApi());
    await saveCurrent({ ...current, request_id: null } as any, "s1", 2, [], STATE, e);
    expect(e.api.saveReviewData).not.toHaveBeenCalled();
    expect(e.dispatch).not.toHaveBeenCalled();
  });
});

describe("closeCurrent", () => {
  it("closes the PR and advances", async () => {
    const api = fakeApi({ navigateToEntry: vi.fn(async () => ({ data: cardData({ entry_number: 3 }) })) });
    const e = fakeEffects(api);
    await closeCurrent(current, "s1", 2, STATE, e);

    expect(e.trackClose).toHaveBeenCalledWith("req-1", "X City");
    expect(api.navigateToEntry).toHaveBeenCalledWith("s1", 3);
  });
});

describe("buildEntry", () => {
  it("marks merged/closed PRs read-only and pulls review_data from fetchReview", async () => {
    const api = fakeApi({ fetchReview: vi.fn(async () => ({ data: { issues: [1] } })) });
    const merged = await buildEntry(cardData({ pr: { url: "u", status: "merged", reviewState: null, number: 5 } }), api);
    expect(merged.is_read_only).toBe(true);
    expect(merged.review_data).toEqual({ issues: [1] });

    const open = await buildEntry(cardData(), api);
    expect(open.is_read_only).toBe(false);
  });
});
