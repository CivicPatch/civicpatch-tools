// One person's memberships, grouped the way the editor shows them: a section per organization,
// their posts inside it. A person can hold one open membership per organization, so a section is
// usually one line, and the grouping is what makes two bodies read as two commitments rather than
// one list of posts.

import {
  MEMBERSHIP_REMOVAL,
  type MembershipRemoval,
  type RosterMembership,
} from "../../schemas/membership-removal.js";

export interface OrganizationMemberships {
  organizationId: string;
  organizationName: string;
  memberships: RosterMembership[];
}

export function membershipsByOrganization(
  rows: RosterMembership[],
  personId: string,
): OrganizationMemberships[] {
  const sections = new Map<string, OrganizationMemberships>();
  for (const row of rows) {
    if (row.person_id !== personId) continue;
    const section = sections.get(row.organization_id);
    if (section) section.memberships.push(row);
    else
      sections.set(row.organization_id, {
        organizationId: row.organization_id,
        organizationName: row.organization_name,
        memberships: [row],
      });
  }
  return [...sections.values()].sort((a, b) =>
    a.organizationName.localeCompare(b.organizationName),
  );
}

export function membershipTitle(membership: RosterMembership): string {
  return membership.label || membership.post_label;
}

// Picking the claim already made withdraws it. The two claims contradict each other, so the
// server withdraws the other one itself and the screen never has to send two requests.
export function nextRemoval(
  current: MembershipRemoval,
  act: MembershipRemoval,
): MembershipRemoval {
  return current === act ? MEMBERSHIP_REMOVAL.NONE : act;
}
