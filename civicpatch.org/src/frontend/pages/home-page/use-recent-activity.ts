import { useEffect, useState } from "haunted";
import { fetchChangeLogs } from "../../api.js";

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
}

// Same endpoint the /activity page uses, not a bespoke query — see
// project plan: the point is that this widget inherits new activity kinds
// (e.g. future pipeline events) automatically, with nothing to update here.
const AUTHORS_ALL = "all";
const RECENT_ACTIVITY_PAGE_SIZE = 10;

export function useRecentActivity() {
  const [entries, setEntries] = useState<RecentActivityEntry[]>([]);

  useEffect(() => {
    fetchChangeLogs(AUTHORS_ALL, 1, RECENT_ACTIVITY_PAGE_SIZE)
      .then((d: any) => setEntries(d.data ?? []))
      .catch(() => {});
  }, []);

  return { entries };
}
