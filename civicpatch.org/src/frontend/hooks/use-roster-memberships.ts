import { fetchMemberships } from "../api.js";
import type { RosterMembership } from "../schemas/roster-membership.js";
import { useAsyncData } from "./use-async-data.js";

const NO_MEMBERSHIPS: RosterMembership[] = [];

export interface RosterMemberships {
  memberships: RosterMembership[];
}

/** A jurisdiction's open memberships, and the one write the editor makes against them.
 *
 * Reloading rather than patching the row locally: the server decides which claim a choice
 * withdraws, so the answer it returns is the only one worth showing.
 */
export function useRosterMemberships(
  jurisdictionOcdid: string | null | undefined,
  changesetId: string | null = null,
): RosterMemberships {
  const { data, reload } = useAsyncData<RosterMembership[]>(async () => {
    if (!jurisdictionOcdid) return [];
    const body = await fetchMemberships(jurisdictionOcdid);
    return body.data.memberships;
  }, [jurisdictionOcdid]);
  return { memberships: data ?? NO_MEMBERSHIPS };
}
