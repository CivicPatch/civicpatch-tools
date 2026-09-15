import type { Organization } from "../../components/organizations-list/organizations-model.js";
import { heldPost, type Post } from "../../components/posts-list/posts-model.js";
import { personOf, type PersonCard } from "../../components/people/person-cards.js";

export interface OrganizationGroup {
  organization: Organization;
  cards: PersonCard[];
}

// A card's organization, resolved once per render and reused both for grouping (below) and
// for scoping that person's office-picker options and post-add target.
export interface CardOrganization {
  organizationId: string;
  posts: Post[];
}

function organizationIdFor(
  card: PersonCard,
  orgIdByPostId: Map<string, string>,
  addedUnderOrg: Map<string, string>,
  fallbackOrgId: string,
): string {
  const held = heldPost(personOf(card)?.memberships);
  const heldOrgId = held?.post_id ? orgIdByPostId.get(held.post_id) : undefined;
  return heldOrgId ?? addedUnderOrg.get(card.personId) ?? fallbackOrgId;
}

/** Every card, sorted into the organization its held post belongs to — or, for someone with
 * none yet, wherever "Add" was clicked for them this session, falling back to the
 * jurisdiction's first-sorted organization (its default body, by construction of
 * `list_for_jurisdiction`'s own ordering) for a person nobody has placed at all. */
export function groupCardsByOrganization(
  cards: PersonCard[],
  organizations: Organization[],
  addedUnderOrg: Map<string, string>,
): OrganizationGroup[] {
  const orgIdByPostId = new Map<string, string>();
  for (const organization of organizations) {
    for (const post of organization.posts) orgIdByPostId.set(post.id, organization.id);
  }
  const fallbackOrgId = organizations[0]?.id ?? "";
  const cardsByOrgId = new Map<string, PersonCard[]>(
    organizations.map((organization) => [organization.id, []]),
  );
  for (const card of cards) {
    const orgId = organizationIdFor(card, orgIdByPostId, addedUnderOrg, fallbackOrgId);
    cardsByOrgId.get(orgId)?.push(card);
  }
  return organizations.map((organization) => ({
    organization,
    cards: cardsByOrgId.get(organization.id) ?? [],
  }));
}

/** The same placement, as a per-person lookup — for building each card's editor props with
 * that organization's own posts rather than every organization's combined list. */
export function cardOrganizationsById(
  groups: OrganizationGroup[],
): Map<string, CardOrganization> {
  const byPersonId = new Map<string, CardOrganization>();
  for (const group of groups) {
    for (const card of group.cards) {
      byPersonId.set(card.personId, {
        organizationId: group.organization.id,
        posts: group.organization.posts,
      });
    }
  }
  return byPersonId;
}
