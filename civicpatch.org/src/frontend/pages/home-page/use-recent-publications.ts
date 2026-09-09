import { useEffect, useState } from "haunted";
import { fetchRecentPublications } from "../../api.js";

export interface RecentPublication {
  jurisdiction_ocdid: string;
  jurisdiction_name: string | null;
  state: string | null;
  author_name: string;
  author_role: string;
  commit_url: string | null;
  created_at: string;
  review_count: number;
}

export function useRecentPublications() {
  const [recentPublications, setRecentPublications] = useState<
    RecentPublication[]
  >([]);

  useEffect(() => {
    fetchRecentPublications()
      .then((d: any) => setRecentPublications(d.data ?? []))
      .catch(() => {});
  }, []);

  return { recentPublications };
}
