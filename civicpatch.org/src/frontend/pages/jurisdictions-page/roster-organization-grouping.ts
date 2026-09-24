import type { Organization } from "../../components/organizations-list/organizations-model.js";
import type { PersonCard } from "../../components/people/person-cards.js";

export interface OrganizationGroup {
  organization: Organization;
  cards: PersonCard[];
}

/** The jurisdiction's organizations, each with the rows about it.
 *
 * A plain group-by since 2026-09-24: `buildPersonCards` emits one row per body and each row
 * carries its own `organizationId`, so there is nothing left to resolve here. It used to place
 * the cards itself — mapping a held post back to its organization, cloning the card per body,
 * and stamping a removed status — which was a second place deciding what a row is about.
 *
 * Somebody with no office yet has no body to be placed in, so they go wherever "Add" was
 * clicked for them this session, falling back to the jurisdiction's first-sorted organization
 * (its default body, by construction of `list_for_jurisdiction`'s own ordering).
 */
export function groupCardsByOrganization(
  cards: PersonCard[],
  organizations: Organization[],
  addedUnderOrg: Map<string, string>,
): OrganizationGroup[] {
  const fallbackOrgId = organizations[0]?.id ?? "";
  const cardsByOrgId = new Map<string, PersonCard[]>(
    organizations.map((organization) => [organization.id, []]),
  );
  for (const card of cards) {
    const orgId =
      card.organizationId ??
      addedUnderOrg.get(card.personId) ??
      fallbackOrgId;
    cardsByOrgId.get(orgId)?.push(
      card.organizationId ? card : { ...card, organizationId: orgId },
    );
  }
  return organizations.map((organization) => ({
    organization,
    cards: cardsByOrgId.get(organization.id) ?? [],
  }));
}
