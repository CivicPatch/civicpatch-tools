import type { Post } from "../posts-list/posts-model.js";

// Everyone who holds or held it: a held post cannot be deleted outright.
export type OrganizationPost = Post & { holder_names: string[] };

export interface Organization {
  id: string;
  name: string;
  url: string | null;
  sort_order: number;
  meta_is_default: boolean;
  posts: OrganizationPost[];
}

// Mirrors database/organizations.py `get_default`: the list arrives in its fallback order.
export const defaultOrganizationId = (organizations: Organization[]): string | null =>
  (organizations.find((organization) => organization.meta_is_default) ?? organizations[0])?.id ??
  null;

// Mirrors core/post_deletion.py `merge_refusal`: same role and division, another organization.
export const mergeTargets = (organizations: Organization[], post: Post): Post[] =>
  organizations
    .filter((organization) => organization.id !== post.organization_id)
    .flatMap((organization) => organization.posts)
    .filter(
      (other) => other.role_id === post.role_id && other.division_ocdid === post.division_ocdid,
    );
