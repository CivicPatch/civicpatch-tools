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

/** How the page worded this post, where that is not what the title already says.
 *
 * The title is the post's own name, composed from the decided role and division
 * (`derive_post_label`); `sources` is the page's own phrasing, stored verbatim. They differ by
 * an abbreviation as often as not ("Mayor Pro Tempore, District 4" against "Mayor Pro Tem
 * District 4"), which reads as a duplicate rather than as two different things, so an identical
 * one is dropped and the rest are labelled.
 */
export function pageWordings(
  membership: RosterMembership,
  title: string,
): string[] {
  const seen = new Set<string>();
  return (membership.source_labels ?? []).filter((wording) => {
    if (!wording || wording === title || seen.has(wording)) return false;
    seen.add(wording);
    return true;
  });
}

// Picking the claim already made withdraws it. The two claims contradict each other, so the
// server withdraws the other one itself and the screen never has to send two requests.
export function nextRemoval(
  current: MembershipRemoval,
  act: MembershipRemoval,
): MembershipRemoval {
  return current === act ? MEMBERSHIP_REMOVAL.NONE : act;
}
