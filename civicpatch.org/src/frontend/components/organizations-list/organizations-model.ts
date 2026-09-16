import type { Post } from "../posts-list/posts-model.js";

export interface Organization {
  id: string;
  name: string;
  url: string | null;
  sort_order: number;
  meta_is_default: boolean;
  posts: Post[];
}

// Mirrors database/organizations.py `get_default`: the list arrives in its fallback order.
export const defaultOrganizationId = (organizations: Organization[]): string | null =>
  (organizations.find((organization) => organization.meta_is_default) ?? organizations[0])?.id ??
  null;
