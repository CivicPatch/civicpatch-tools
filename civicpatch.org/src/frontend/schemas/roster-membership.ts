// The shape the roster read hands back for one membership. Mirrors `database/memberships.py`'s
// `list_by_person` — the two languages keep their own copy since neither can import the other.

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
}
