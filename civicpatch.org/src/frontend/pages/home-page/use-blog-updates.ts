import { useEffect, useState } from "haunted";
import { fetchBlogPosts } from "../../api.js";

export interface BlogUpdate {
  slug: string;
  title: string;
  date: string;
  description: string;
  author: string;
}

export function useBlogUpdates() {
  const [blogUpdates, setBlogUpdates] = useState<BlogUpdate[]>([]);

  useEffect(() => {
    fetchBlogPosts()
      .then((d: any) => setBlogUpdates(d.data ?? []))
      .catch(() => {});
  }, []);

  return { blogUpdates };
}
