import type { Post } from "../posts-list/posts-model.js";

export interface Organization {
  id: string;
  name: string;
  url: string | null;
  sort_order: number;
  posts: Post[];
}
