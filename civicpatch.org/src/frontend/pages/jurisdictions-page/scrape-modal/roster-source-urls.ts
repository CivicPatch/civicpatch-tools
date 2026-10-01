export interface RosterSourceUrls {
  organization_id: string;
  organization_name: string;
  urls: string[];
}

/** Every url once, in the order shown: what the modal sends. */
export function flattenSourceUrls(groups: RosterSourceUrls[]): string[] {
  return [...new Set(groups.flatMap((group) => group.urls))];
}
