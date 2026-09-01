import { fetchPosts } from "../api.js";
import type { Post } from "../components/posts-list/posts-model.js";
import { useAsyncData } from "./use-async-data.js";

// One array, not a fresh literal per render: this is bound as a property on `person-editor-list`,
// and a new identity each render is a changed prop, which re-renders, which mints another.
const NO_POSTS: Post[] = [];

/** Every post in a jurisdiction, for the editor's Post field. A hook because two pages mount
 * the same editor; empty while loading and on failure, when the control shows the record's value. */
export function useJurisdictionPosts(
  jurisdictionOcdid: string | null | undefined,
): Post[] {
  const { data } = useAsyncData<Post[]>(async () => {
    if (!jurisdictionOcdid) return [];
    const body = await fetchPosts(jurisdictionOcdid);
    return body.data.organizations
      .flatMap((organization: { posts: Post[] }) => organization.posts)
      .sort((a: Post, b: Post) => a.label.localeCompare(b.label));
  }, [jurisdictionOcdid]);
  return data ?? NO_POSTS;
}
