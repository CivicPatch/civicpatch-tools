// Mirrors `schemas/review_cards.py` ReviewCard and `core/review_summary.py` ReviewSummary.

import type { Issue } from "../components/fields/field-model.js";
import type { PersonClaim } from "../components/person-editor/field-provenance.js";
import type { Post } from "../components/posts-list/posts-model.js";

export interface RosterPresence {
  name: string;
  in_research: boolean;
  in_data: boolean;
}

export interface ReviewSummary {
  issues: Issue[];
  people_by_source: RosterPresence[];
}

export interface ReviewSource {
  url: string;
  markdown: string | null;
  html: string | null;
  // When the pipeline stored the copy this url opens, whether or not it was this scrape's.
  cached_at: string | null;
  is_cached_by_this_scrape: boolean;
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
  sources: ReviewSource[];
  // Which of the card's organizations this changeset read a page for.
  organizations_read: string[];
  overridden_source_values: Record<string, Record<string, unknown>>;
  review: ReviewSummary;
  organizations: CardOrganization[];
  claims: Record<string, PersonClaim[]>;
}
