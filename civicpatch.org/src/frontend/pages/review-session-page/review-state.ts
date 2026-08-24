// The review-session state: a tiny reducer with three states — loading the
// card, looking at a card, or broke. The async (fetching cards, ending the
// session, redirecting) lives in use-review-session.ts; this file is pure.
//
// No stale-request token is needed: a navbar state switch is a full page reload
// (route split), and within a session navigation is serialized by `busy` — a
// second advance while busy is ignored — so two fetches never overlap.
//
// snake_case keys cross the hook → page → component boundary and match the API
// contract (see CLAUDE.md).

import type { ProposedChange } from "../../components/people/person-cards.js";

export const StateKind = {
  LOADING: "loading",
  REVIEWING: "reviewing",
  ERROR: "error",
} as const;

export const ActionType = {
  NAV_STARTED: "nav_started",
  SESSION_LOADED: "session_loaded",
  ENTRY_LOADED: "entry_loaded",
  MARK_RESOLVED: "mark_resolved",
  MARK_SAVED: "mark_saved",
  MARK_FAILED: "mark_failed",
  LOAD_FAILED: "load_failed",
  STATS_LOADED: "stats_loaded",
} as const;

// baseline = first capture for a jurisdiction (nothing to diff against);
// reconcile = subsequent scrape (old<->new pairing is meaningful). Mirrors the
// backend ReviewMode enum; the API sends `mode` on the navigate response.
export const ReviewMode = {
  BASELINE: "baseline",
  RECONCILE: "reconcile",
} as const;
export type ReviewModeValue = typeof ReviewMode[keyof typeof ReviewMode];

// The data for the entry currently displayed in the review card.
export type CurrentEntry = {
  request_id: string;
  jurisdiction: { ocdid: string | null; name: string | null; path?: string | null; website_url?: string | null };
  pr: { url: string | null; status: string | null; reviewState: string | null; number?: number | null };
  mode: ReviewModeValue;
  pr_people: { existing: any[]; proposed: any[] };
  changes?: ProposedChange[];
  review_data: any;
  source_content_urls: any[];
  is_read_only: boolean;
  has_next: boolean;
};

export type SessionMeta = { id: string; daily_goal: number };

export type Stats = {
  today_resolved: number;
  streak: number;
  all_time_resolved: number;
  available_count: number;
  claimed_count: number;
  best_streak: number;
  avg_seconds_per_review: number | null;
};

export const DEFAULT_STATS: Stats = {
  today_resolved: 0,
  streak: 0,
  all_time_resolved: 0,
  available_count: 0,
  claimed_count: 0,
  best_streak: 0,
  avg_seconds_per_review: null,
};

export type ReviewState =
  | { kind: typeof StateKind.LOADING; state_code: string }
  | {
      kind: typeof StateKind.REVIEWING;
      state_code: string;
      // null for a deep-linked lone PR (no resumable session); the card shows
      // "Exit" instead of the Back/Next/dots/End controls.
      session: SessionMeta | null;
      current_entry: CurrentEntry;
      entry_number: number;
      resolved_entry_numbers: Set<number>;
      // Entries committed to the branch but not published. Session-local like
      // failed_entries — the server holds the card for the session's lifetime, so
      // a reload showing them as merely visited is accurate enough.
      saved_entry_numbers: Set<number>;
      // Entries whose publish was rejected for a reason we caught synchronously
      // (bad input / save error), entry_number -> error message. Drives the red
      // dot + the error banner; session-local (a reload re-encounters it unresolved).
      failed_entries: Map<number, string>;
      frontier_entry: number;
      // Session length, computed server-side per navigate (goal capped by what's
      // reviewable). The client renders this; it does not derive its own count.
      total: number;
      busy: boolean;
    }
  | { kind: typeof StateKind.ERROR; state_code: string; message: string };

export type PageState = { fsm: ReviewState; stats: Stats };

export type ReviewAction =
  | { type: typeof ActionType.NAV_STARTED }
  // First card of the page — boot or deep-link. Establishes session context
  // (session is null for a deep-link).
  | {
      type: typeof ActionType.SESSION_LOADED;
      payload: { current_entry: CurrentEntry; entry_number: number; total: number; session: SessionMeta | null; resolved_entry_numbers: number[] };
    }
  // A subsequent within-session navigation — reuses the current session/resolved.
  | { type: typeof ActionType.ENTRY_LOADED; payload: { current_entry: CurrentEntry; entry_number: number; total: number } }
  | { type: typeof ActionType.MARK_RESOLVED }
  | { type: typeof ActionType.MARK_SAVED }
  | { type: typeof ActionType.MARK_FAILED; payload: { entry_number: number; message: string } }
  | { type: typeof ActionType.LOAD_FAILED; payload: { message: string } }
  | { type: typeof ActionType.STATS_LOADED; payload: { stats: Stats } };

export function initialPageState(stateCode: string): PageState {
  return { fsm: { kind: StateKind.LOADING, state_code: stateCode }, stats: DEFAULT_STATS };
}

function reviewingFrom(
  state: PageState,
  args: { session: SessionMeta | null; current_entry: CurrentEntry; entry_number: number; total: number; resolved_entry_numbers: Set<number>; saved_entry_numbers: Set<number>; failed_entries: Map<number, string> },
): PageState {
  const prevFrontier = state.fsm.kind === StateKind.REVIEWING ? state.fsm.frontier_entry : 0;
  return {
    ...state,
    fsm: {
      kind: StateKind.REVIEWING,
      state_code: state.fsm.state_code,
      session: args.session,
      current_entry: args.current_entry,
      entry_number: args.entry_number,
      resolved_entry_numbers: args.resolved_entry_numbers,
      saved_entry_numbers: args.saved_entry_numbers,
      failed_entries: args.failed_entries,
      frontier_entry: Math.max(prevFrontier, args.entry_number),
      total: args.total,
      busy: false,
    },
  };
}

export function reduceReview(state: PageState, action: ReviewAction): PageState {
  const fsm = state.fsm;
  switch (action.type) {
    case ActionType.NAV_STARTED:
      if (fsm.kind !== StateKind.REVIEWING) return state;
      return { ...state, fsm: { ...fsm, busy: true } };

    case ActionType.SESSION_LOADED:
      return reviewingFrom(state, {
        session: action.payload.session,
        current_entry: action.payload.current_entry,
        entry_number: action.payload.entry_number,
        total: action.payload.total,
        resolved_entry_numbers: new Set(action.payload.resolved_entry_numbers),
        saved_entry_numbers: new Set(),
        failed_entries: new Map(),
      });

    case ActionType.ENTRY_LOADED:
      if (fsm.kind !== StateKind.REVIEWING) return state;
      return reviewingFrom(state, {
        session: fsm.session,
        current_entry: action.payload.current_entry,
        entry_number: action.payload.entry_number,
        total: action.payload.total,
        resolved_entry_numbers: fsm.resolved_entry_numbers,
        saved_entry_numbers: fsm.saved_entry_numbers,
        failed_entries: fsm.failed_entries,
      });

    case ActionType.MARK_RESOLVED: {
      if (fsm.kind !== StateKind.REVIEWING) return state;
      const failed = new Map(fsm.failed_entries);
      failed.delete(fsm.entry_number); // a successful (re)publish clears the red flag
      const saved = new Set(fsm.saved_entry_numbers);
      saved.delete(fsm.entry_number); // publishing a saved card promotes it out of saved
      return {
        ...state,
        fsm: {
          ...fsm,
          resolved_entry_numbers: new Set([...fsm.resolved_entry_numbers, fsm.entry_number]),
          saved_entry_numbers: saved,
          failed_entries: failed,
        },
      };
    }

    case ActionType.MARK_SAVED: {
      if (fsm.kind !== StateKind.REVIEWING) return state;
      const failed = new Map(fsm.failed_entries);
      failed.delete(fsm.entry_number); // a successful save clears an earlier red flag
      return {
        ...state,
        fsm: {
          ...fsm,
          saved_entry_numbers: new Set([...fsm.saved_entry_numbers, fsm.entry_number]),
          failed_entries: failed,
        },
      };
    }

    case ActionType.MARK_FAILED: {
      if (fsm.kind !== StateKind.REVIEWING) return state;
      const failed = new Map(fsm.failed_entries);
      failed.set(action.payload.entry_number, action.payload.message);
      return { ...state, fsm: { ...fsm, failed_entries: failed } };
    }

    case ActionType.LOAD_FAILED:
      return { ...state, fsm: { kind: StateKind.ERROR, state_code: fsm.state_code, message: action.payload.message } };

    case ActionType.STATS_LOADED:
      return { ...state, stats: action.payload.stats };

    default:
      return state;
  }
}
