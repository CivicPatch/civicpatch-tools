// Mirrors `schemas/review_cards.py` ReviewCard and `core/review_summary.py` ReviewSummary.

import type { Issue } from "../components/fields/field-model.js";
import type { PersonAssertion } from "../components/person-editor/field-provenance.js";
import type { Post } from "../components/posts-list/posts-model.js";
import type { ProposedChange } from "./membership-proposal.js";

export interface RosterPresence {
  name: string;
  in_research: boolean;
  in_data: boolean;
}

export interface ReviewSummary {
  issues: Issue[];
  people_by_source: RosterPresence[];
  origin_source: string | null;
}

export interface ReviewSource {
  url: string;
  markdown: string | null;
}

// `GET /organizations/{ocdid}`'s shape: each organization with its posts.
export interface CardOrganization {
  id: string;
  name: string;
  posts: Post[];
}

export interface ReviewCard {
  changeset_id: string;
  jurisdiction_ocdid: string;
  existing: any[];
  proposed: any[];
  changes: ProposedChange[];
  sources: ReviewSource[];
  overridden_source_values: Record<string, Record<string, unknown>>;
  review: ReviewSummary;
  organizations: CardOrganization[];
  assertions: Record<string, PersonAssertion[]>;
}
