// What a person can claim about a membership, and the shape the roster read hands back for one.
// Mirrors `schemas/posts.py::MembershipRemovalAssertion` and `database/memberships.py`'s
// `list_by_person` — the two languages keep their own copy since neither can import the other.

// The three contradict each other, so a request names which one is chosen and the server
// withdraws the others. `NONE` is the withdraw.
export const MEMBERSHIP_REMOVAL = {
  NONE: "none",
  CLOSED: "closed",
  NEVER_HELD: "never_held",
} as const;
export type MembershipRemoval =
  (typeof MEMBERSHIP_REMOVAL)[keyof typeof MEMBERSHIP_REMOVAL];

export interface RosterMembership {
  id: string;
  person_id: string;
  post_id: string;
  organization_id: string;
  organization_name: string;
  post_label: string;
  // The name a human gave this person's post, else null and `post_label` stands in.
  label: string | null;
  source_labels: string[];
  removal_assertion: MembershipRemoval;
}
