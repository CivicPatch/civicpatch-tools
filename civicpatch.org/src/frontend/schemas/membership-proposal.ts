// Membership vocabulary the frontend shares with the review proposal. Mirrors
// `core/membership_proposal.py` — the two languages keep their own copy since neither can
// import the other, but each side names this in exactly one place.

export const MEMBERSHIP_DISPOSITION = {
  UNCHANGED: "unchanged",
  NEW: "new",
  MOVED: "moved",
  ABSENT: "absent",
} as const;
export type MembershipDisposition =
  (typeof MEMBERSHIP_DISPOSITION)[keyof typeof MEMBERSHIP_DISPOSITION];

// The post a membership is in, or would be in. `id` is null for one this scrape would create.
export interface MembershipPost {
  id: string | null;
  role_id: string;
  role_label: string;
  division_ocdid: string;
  // The name a human gave the post, else composed from role and division. Display only.
  label: string;
  meta_is_tracked: boolean;
}

// The only source for "which post would this person land in" — they hold no membership yet.
export interface ProposedChange {
  person_id: string;
  organization_id: string;
  disposition: MembershipDisposition;
  // For "absent", the post they would leave.
  post: MembershipPost;
  membership_label: string | null;
  // "moved" only: the post they would leave.
  from_post: MembershipPost | null;
}
