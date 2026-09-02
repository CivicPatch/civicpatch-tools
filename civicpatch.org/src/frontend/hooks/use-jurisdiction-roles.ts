import { fetchRoles } from "../api.js";
import type { RoleOption } from "../components/posts-list/posts-model.js";
import { useAsyncData } from "./use-async-data.js";

// One array, not a fresh literal per render — same reason as `use-jurisdiction-posts`: this is
// bound as a property, and a new identity each render is a changed prop.
const NO_ROLES: RoleOption[] = [];

/** The role vocabulary, for the post-add form. Jurisdiction-independent — roles are global —
 * but the hook keeps the call out of the page. Empty while loading and on failure, which
 * leaves the form's role select with nothing to choose and its save guarded on `NO_ROLE`. */
export function useJurisdictionRoles(): RoleOption[] {
  const { data } = useAsyncData<RoleOption[]>(async () => {
    const body = await fetchRoles();
    return body.data?.roles ?? [];
  }, []);
  return data ?? NO_ROLES;
}
