import { fetchRoles } from "../api.js";
import type { RoleOption } from "../components/posts-list/posts-model.js";
import { useAsyncData } from "./use-async-data.js";

// One array, not a fresh literal per render — same reason as `use-jurisdiction-posts`: this is
// bound as a property, and a new identity each render is a changed prop.
const NO_ROLES: RoleOption[] = [];

/** A jurisdiction's roles, for the post-add form. Empty until the first load, which leaves the
 * form's role select with nothing to choose; a changed jurisdiction keeps the old list until its own arrives. */
export function useJurisdictionRoles(jurisdictionOcdid: string): RoleOption[] {
  const { data } = useAsyncData<RoleOption[]>(async () => {
    if (!jurisdictionOcdid) return NO_ROLES;
    const body = await fetchRoles({ jurisdictionOcdid });
    return body.data?.roles ?? [];
  }, [jurisdictionOcdid]);
  return data ?? NO_ROLES;
}

/** Every role, to sort people on pages that mix jurisdictions and offer no post-add form. */
export function useEveryRole(): RoleOption[] {
  const { data } = useAsyncData<RoleOption[]>(async () => {
    const body = await fetchRoles();
    return body.data?.roles ?? [];
  }, []);
  return data ?? NO_ROLES;
}
