import { fetchMemberships } from "../api.js";
import { officeOptions } from "../components/posts-list/posts-model.js";
import type { OfficeOption } from "../components/posts-list/posts-model.js";
import { useAsyncData } from "./use-async-data.js";

/** Every office a jurisdiction already has, for the editor's office field to be picked from.
 *
 * A hook rather than a prop because two pages mount the same editor — the review session and
 * the jurisdiction page — and neither owns this data more than the other.
 *
 * Returns `[]` while loading and on failure, which the control is written for: it still shows
 * whatever the record says, so a slow or broken read makes the field un-editable rather than
 * making it look empty.
 */
export function useOfficeOptions(
  jurisdictionOcdid: string | null | undefined,
): OfficeOption[] {
  const { data } = useAsyncData<OfficeOption[]>(async () => {
    if (!jurisdictionOcdid) return [];
    const body = await fetchMemberships(jurisdictionOcdid);
    return officeOptions(body.data.memberships);
  }, [jurisdictionOcdid]);
  return data ?? [];
}
