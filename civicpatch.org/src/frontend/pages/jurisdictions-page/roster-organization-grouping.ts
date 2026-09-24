import type { Organization } from "../../components/organizations-list/organizations-model.js";
import {
  cardKey,
  personOf,
  PersonStatus,
  type PersonCard,
} from "../../components/people/person-cards.js";

export interface OrganizationGroup {
  organization: Organization;
  cards: PersonCard[];
}

/** Every body this card belongs under: one per office they hold, since somebody may sit on
 * several. Resolved through the post rather than the membership's own `organization_id`, so a
 * card shape that carries only posts still places correctly.
 *
 * Until 2026-09-23 this answered with a single body and `heldPost` gave up on anyone holding
 * two, so a person on two bodies was filed silently under the default one. */
function organizationIdsFor(
  card: PersonCard,
  orgIdByPostId: Map<string, string>,
  addedUnderOrg: Map<string, string>,
  fallbackOrgId: string,
): string[] {
  const held = personOf(card)?.memberships ?? [];
  const bodies = [
    ...new Set(
      held
        .map((membership) => orgIdByPostId.get(membership.post_id))
        .filter((id): id is string => !!id),
    ),
  ];
  if (bodies.length) return bodies;
  // Nobody has placed them yet: wherever "Add" was clicked, else the default body.
  return [addedUnderOrg.get(card.personId) ?? fallbackOrgId];
}

/** Every card, sorted into the organization its held post belongs to — or, for someone with
 * none yet, wherever "Add" was clicked for them this session, falling back to the
 * jurisdiction's first-sorted organization (its default body, by construction of
 * `list_for_jurisdiction`'s own ordering) for a person nobody has placed at all. */
export function groupCardsByOrganization(
  cards: PersonCard[],
  organizations: Organization[],
  addedUnderOrg: Map<string, string>,
  removedKeys: Set<string> = new Set(),
): OrganizationGroup[] {
  const orgIdByPostId = new Map<string, string>();
  for (const organization of organizations) {
    for (const post of organization.posts)
      orgIdByPostId.set(post.id, organization.id);
  }
  const fallbackOrgId = organizations[0]?.id ?? "";
  const cardsByOrgId = new Map<string, PersonCard[]>(
    organizations.map((organization) => [organization.id, []]),
  );
  for (const card of cards) {
    for (const orgId of organizationIdsFor(
      card,
      orgIdByPostId,
      addedUnderOrg,
      fallbackOrgId,
    )) {
      const row = { ...card, organizationId: orgId };
      cardsByOrgId
        .get(orgId)
        ?.push(
          removedKeys.has(cardKey(row))
            ? { ...row, status: PersonStatus.DELETED }
            : row,
        );
    }
  }
  return organizations.map((organization) => ({
    organization,
    cards: cardsByOrgId.get(organization.id) ?? [],
  }));
}
