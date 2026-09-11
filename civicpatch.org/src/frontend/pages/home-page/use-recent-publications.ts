import { useEffect, useState } from "haunted";
import { fetchRecentPublications } from "../../api.js";

export interface RecentPublication {
  jurisdiction_ocdid: string;
  jurisdiction_name: string | null;
  state: string | null;
  commit_url: string | null;
  kind: string | null;
  created_at: string;
  review_count: number;
}

// 20, not the default 10 — closer (doesn't have to be exact) to how many rows
// coverage-by-state renders beside it, so the two panels read as roughly the same size.
const RECENT_PUBLICATIONS_LIMIT = 20;

export function useRecentPublications() {
  const [recentPublications, setRecentPublications] = useState<
    RecentPublication[]
  >([]);

  useEffect(() => {
    fetchRecentPublications(RECENT_PUBLICATIONS_LIMIT)
      .then((d: any) => setRecentPublications(d.data ?? []))
      .catch(() => {});
  }, []);

  return { recentPublications };
}
