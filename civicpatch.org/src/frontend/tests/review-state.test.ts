import { describe, it, expect } from "vitest";
import {
  initialPageState,
  reduceReview,
  DEFAULT_STATS,
  type CurrentEntry,
  type PageState,
  type SessionMeta,
} from "../pages/review-session-page/review-state.ts";

const SESSION: SessionMeta = { id: "session-1", daily_goal: 10 };

function entry(requestId = "req-1"): CurrentEntry {
  return {
    request_id: requestId,
    jurisdiction: { ocdid: "ocd-jurisdiction/country:us/state:nj/place:x", name: "X City", path: null },
    pr: { url: "https://example/pr/3", status: "open", reviewState: null, number: 3 },
    pr_people: { existing: [], proposed: [] },
    review_data: null,
    source_content_urls: [],
    is_read_only: false,
    has_next: true,
  };
}

// A reviewing state at entry `n` with the given resolved set and frontier.
function reviewing(n: number, resolved: number[] = [], frontier = n): PageState {
  return {
    fsm: {
      kind: "reviewing",
      state_code: "nj",
      session: SESSION,
      current_entry: entry(),
      entry_number: n,
      resolved_entry_numbers: new Set(resolved),
      failed_entries: new Map(),
      frontier_entry: frontier,
      total: 10,
      busy: false,
    },
    stats: DEFAULT_STATS,
  };
}

describe("reduceReview", () => {
  it("initialPageState starts in loading with default stats", () => {
    const state = initialPageState("nj");
    expect(state.fsm).toEqual({ kind: "loading", state_code: "nj" });
    expect(state.stats).toBe(DEFAULT_STATS);
  });

  it("session_loaded with a session enters reviewing at the loaded entry", () => {
    const next = reduceReview(initialPageState("nj"), {
      type: "session_loaded",
      payload: { current_entry: entry(), entry_number: 2, total: 5, session: SESSION, resolved_entry_numbers: [1] },
    });
    expect(next.fsm.kind).toBe("reviewing");
    if (next.fsm.kind !== "reviewing") throw new Error("unreachable");
    expect(next.fsm.session).toBe(SESSION);
    expect(next.fsm.entry_number).toBe(2);
    expect(next.fsm.total).toBe(5);
    expect(next.fsm.frontier_entry).toBe(2);
    expect([...next.fsm.resolved_entry_numbers]).toEqual([1]);
    expect(next.fsm.busy).toBe(false);
  });

  it("session_loaded with a null session (deep-link) enters reviewing with no session", () => {
    const next = reduceReview(initialPageState("nj"), {
      type: "session_loaded",
      payload: { current_entry: entry(), entry_number: 1, total: 1, session: null, resolved_entry_numbers: [] },
    });
    if (next.fsm.kind !== "reviewing") throw new Error("expected reviewing");
    expect(next.fsm.session).toBeNull();
  });

  it("nav_started sets busy on a reviewing state", () => {
    const next = reduceReview(reviewing(2), { type: "nav_started" });
    if (next.fsm.kind !== "reviewing") throw new Error("expected reviewing");
    expect(next.fsm.busy).toBe(true);
  });

  it("entry_loaded reuses session and resolved set, clears busy", () => {
    const busy = reduceReview(reviewing(2, [1]), { type: "nav_started" });
    const next = reduceReview(busy, { type: "entry_loaded", payload: { current_entry: entry("req-2"), entry_number: 3, total: 7 } });
    if (next.fsm.kind !== "reviewing") throw new Error("expected reviewing");
    expect(next.fsm.session).toBe(SESSION);
    expect([...next.fsm.resolved_entry_numbers]).toEqual([1]);
    expect(next.fsm.current_entry.request_id).toBe("req-2");
    expect(next.fsm.entry_number).toBe(3);
    expect(next.fsm.total).toBe(7);
    expect(next.fsm.busy).toBe(false);
  });

  it("frontier never shrinks when navigating backward", () => {
    const next = reduceReview(reviewing(5, [], 5), { type: "entry_loaded", payload: { current_entry: entry(), entry_number: 3, total: 10 } });
    if (next.fsm.kind !== "reviewing") throw new Error("expected reviewing");
    expect(next.fsm.frontier_entry).toBe(5);
  });

  it("mark_resolved adds the current entry number as a fresh Set", () => {
    const before = reviewing(4, [1]);
    const beforeSet = (before.fsm as any).resolved_entry_numbers;
    const next = reduceReview(before, { type: "mark_resolved" });
    if (next.fsm.kind !== "reviewing") throw new Error("expected reviewing");
    expect([...next.fsm.resolved_entry_numbers].sort()).toEqual([1, 4]);
    expect(next.fsm.resolved_entry_numbers).not.toBe(beforeSet);
  });

  it("mark_failed records the entry's error message", () => {
    const next = reduceReview(reviewing(2), { type: "mark_failed", payload: { entry_number: 2, message: "phones: bad" } });
    if (next.fsm.kind !== "reviewing") throw new Error("expected reviewing");
    expect(next.fsm.failed_entries.get(2)).toBe("phones: bad");
  });

  it("mark_resolved clears a prior failed flag for that entry", () => {
    const failed = reduceReview(reviewing(2), { type: "mark_failed", payload: { entry_number: 2, message: "phones: bad" } });
    const next = reduceReview(failed, { type: "mark_resolved" });
    if (next.fsm.kind !== "reviewing") throw new Error("expected reviewing");
    expect(next.fsm.failed_entries.has(2)).toBe(false);
    expect([...next.fsm.resolved_entry_numbers]).toContain(2);
  });

  it("entry_loaded carries failed_entries across navigation", () => {
    const failed = reduceReview(reviewing(2), { type: "mark_failed", payload: { entry_number: 2, message: "phones: bad" } });
    const next = reduceReview(failed, { type: "entry_loaded", payload: { current_entry: entry(), entry_number: 3, total: 10 } });
    if (next.fsm.kind !== "reviewing") throw new Error("expected reviewing");
    expect(next.fsm.failed_entries.get(2)).toBe("phones: bad");
  });

  it("load_failed moves to error from any state", () => {
    const next = reduceReview(reviewing(2), { type: "load_failed", payload: { message: "HTTP 500" } });
    expect(next.fsm).toEqual({ kind: "error", state_code: "nj", message: "HTTP 500" });
  });

  it("stats_loaded refreshes stats without touching the fsm", () => {
    const loading = initialPageState("nj");
    const stats = { ...DEFAULT_STATS, today_resolved: 7 };
    const next = reduceReview(loading, { type: "stats_loaded", payload: { stats } });
    expect(next.stats).toBe(stats);
    expect(next.fsm).toBe(loading.fsm);
  });

  it("nav_started and entry_loaded are no-ops outside reviewing (same reference)", () => {
    const loading = initialPageState("nj");
    expect(reduceReview(loading, { type: "nav_started" })).toBe(loading);
    expect(reduceReview(loading, { type: "entry_loaded", payload: { current_entry: entry(), entry_number: 1, total: 1 } })).toBe(loading);
  });
});
