import { fetchOrganizations } from "../api-organizations.js";
import type { Organization } from "../components/organizations-list/organizations-model.js";
import { useAsyncData } from "./use-async-data.js";

const NO_ORGANIZATIONS: Organization[] = [];

export interface JurisdictionOrganizations {
  organizations: Organization[];
  reload: () => void;
}

/** A jurisdiction's bodies, each with its own posts nested — for the roster editor's
 * per-organization grouping, not just the organizations-list panel. */
export function useOrganizations(
  jurisdictionOcdid: string | null | undefined,
): JurisdictionOrganizations {
  const { data, reload } = useAsyncData<Organization[]>(async () => {
    if (!jurisdictionOcdid) return [];
    const body = await fetchOrganizations(jurisdictionOcdid);
    return body.data.organizations;
  }, [jurisdictionOcdid]);
  return { organizations: data ?? NO_ORGANIZATIONS, reload };
}
