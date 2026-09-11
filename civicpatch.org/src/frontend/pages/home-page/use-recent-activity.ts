import { useCallback, useEffect, useRef, useState } from "haunted";
import { fetchChangeLogs } from "../../api.js";
import { useWebSocket } from "../../hooks/use-websocket.js";
import { ACTIVITY_CHANNEL } from "../../utils/pubsub-channels.js";
import { markFreshEntries } from "./recent-activity.js";

export interface RecentActivityEntry {
  id: string;
  type: string;
  jurisdiction_ocdid: string | null;
  jurisdiction_name: string | null;
  jurisdiction_path: string | null;
  changeset_id: string | null;
  pull_request_url: string | null;
  changes: Record<string, unknown> | null;
  author_name: string;
  author_role: string;
  is_system: boolean;
  created_at: string;
  summary: string;
  // Client-side only, not from the API: true for a row that showed up on a refresh after the
  // reader had already seen the list once — never on the very first load. Lets the row fade in
  // instead of the whole list just silently having different rows in it.
  isFresh: boolean;
}

// Same endpoint the /activity page uses, not a bespoke query — see
// project plan: the point is that this widget inherits new activity kinds
// (e.g. future pipeline events) automatically, with nothing to update here.
const AUTHORS_ALL = "all";
const RECENT_ACTIVITY_PAGE_SIZE = 10;

// A burst (e.g. a state batch settling several runs close together) would otherwise mean one
// refetch per message for a list that only shows the newest 10 anyway. Waiting this long after
// the *last* message before refetching collapses a whole burst into a single refresh.
const LIVE_REFRESH_DEBOUNCE_MS = 2000;

export function useRecentActivity(isSignedIn: boolean) {
  const [entries, setEntries] = useState<RecentActivityEntry[]>([]);
  const seenIds = useRef<Set<string> | null>(null);

  const refresh = useCallback(() => {
    fetchChangeLogs(AUTHORS_ALL, 1, RECENT_ACTIVITY_PAGE_SIZE)
      .then((d: any) => {
        const fetched: Omit<RecentActivityEntry, "isFresh">[] = d.data ?? [];
        setEntries(markFreshEntries(fetched, seenIds.current));
        seenIds.current = new Set(fetched.map((entry) => entry.id));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Logged-in only: this panel only ever renders for a signed-in user, and /ws itself refuses
  // an unauthenticated connection.
  const { data: liveEvent } = useWebSocket(isSignedIn ? ACTIVITY_CHANNEL : null, {
    autoConnect: isSignedIn,
  });

  const debounceTimer = useRef<number | null>(null);
  useEffect(() => {
    if (!liveEvent) return;
    if (debounceTimer.current !== null) {
      window.clearTimeout(debounceTimer.current);
    }
    debounceTimer.current = window.setTimeout(() => {
      debounceTimer.current = null;
      refresh();
    }, LIVE_REFRESH_DEBOUNCE_MS);
    return () => {
      if (debounceTimer.current !== null) {
        window.clearTimeout(debounceTimer.current);
      }
    };
  }, [liveEvent, refresh]);

  return { entries };
}
