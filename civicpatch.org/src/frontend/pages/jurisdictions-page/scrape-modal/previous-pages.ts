export interface RosterPerson {
  id: string;
  memberships: { organization_id: string; source_urls: string[] }[];
}

export interface NamedOrganization {
  id: string;
  name: string;
}

export interface PageGroup {
  organizationName: string;
  urls: string[];
}

const UNKNOWN_ORGANIZATION_NAME = "Other";

/** The pages the published people were read from, one group per organization — what a
 * re-scrape reads when no urls are typed in. A page shared by two organizations is listed
 * once, under the one with the most people on it, so deleting it removes it. */
export function previousPagesByOrganization(
  people: RosterPerson[],
  organizations: NamedOrganization[],
): PageGroup[] {
  const peopleByUrl = new Map<string, Map<string, Set<string>>>();
  for (const person of people) {
    for (const membership of person.memberships) {
      for (const url of membership.source_urls) {
        const byOrganization = peopleByUrl.get(url) ?? new Map<string, Set<string>>();
        const personIds = byOrganization.get(membership.organization_id) ?? new Set<string>();
        personIds.add(person.id);
        byOrganization.set(membership.organization_id, personIds);
        peopleByUrl.set(url, byOrganization);
      }
    }
  }

  const organizationOrder = organizations.map((organization) => organization.id);
  const urlsByOrganization = new Map<string, { url: string; count: number }[]>();
  for (const [url, byOrganization] of peopleByUrl) {
    const owner = mostPeople(byOrganization, organizationOrder);
    const totalPeople = new Set([...byOrganization.values()].flatMap((ids) => [...ids])).size;
    const entries = urlsByOrganization.get(owner) ?? [];
    entries.push({ url, count: totalPeople });
    urlsByOrganization.set(owner, entries);
  }

  const groups: PageGroup[] = organizations.map((organization) => ({
    organizationName: organization.name,
    urls: byMostPeople(urlsByOrganization.get(organization.id) ?? []),
  }));
  const unknown = [...urlsByOrganization.keys()].filter((id) => !organizationOrder.includes(id));
  if (unknown.length) {
    groups.push({
      organizationName: UNKNOWN_ORGANIZATION_NAME,
      urls: byMostPeople(unknown.flatMap((id) => urlsByOrganization.get(id) ?? [])),
    });
  }
  return groups;
}

/** Every url once, in the order shown: what the modal sends. */
export function flattenPages(groups: PageGroup[]): string[] {
  return [...new Set(groups.flatMap((group) => group.urls))];
}

function mostPeople(byOrganization: Map<string, Set<string>>, organizationOrder: string[]): string {
  const rank = (id: string) => {
    const index = organizationOrder.indexOf(id);
    return index === -1 ? organizationOrder.length : index;
  };
  return [...byOrganization.entries()].sort(
    ([idA, peopleA], [idB, peopleB]) => peopleB.size - peopleA.size || rank(idA) - rank(idB),
  )[0][0];
}

function byMostPeople(entries: { url: string; count: number }[]): string[] {
  return [...entries].sort((a, b) => b.count - a.count).map((entry) => entry.url);
}
