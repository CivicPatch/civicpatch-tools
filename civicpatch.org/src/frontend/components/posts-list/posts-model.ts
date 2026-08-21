import { PLACE_LABEL } from "../edit-people/person-edit-utils.js";
import { parseDivision } from "../ocdid-utils.js";
import { jurisdictionToDivisionBase } from "../edit-people/person-edit-utils.js";

// Pure shaping for the posts screen: the API returns posts grouped by body, the screen wants
// them grouped by role. No I/O, so the grouping and the counts are testable without a DOM.

// Only the fields this screen reads. The API returns more; extra keys are ignored.
export interface Post {
  id: string;
  role_id: string;
  division_ocdid: string;
  label: string | null;
  headcount: number;
  holders: number;
  role_label: string;
  _verified: boolean;
}

export interface Membership {
  post_id: string;
  person_name: string | null;
}

export interface PostRow extends Post {
  // Names rather than the `holders` count, because the screen lists people. The count still
  // rides along: it is what `?as_of` answers, and it can disagree with this list when the
  // membership read is undated.
  holder_names: string[];
  over_headcount: boolean;
}

export interface RoleGroup {
  role_id: string;
  role_label: string;
  posts: PostRow[];
  headcount: number;
  filled: number;
  // Unfilled capacity across the role. Negative would mean over-subscribed, which is a
  // per-post problem, so it floors at zero and `over_headcount` carries the anomaly.
  free: number;
}

// A post covering the whole jurisdiction rather than a sub-division. Named because it is a
// domain state, not decoration — it is what `place:` with no ward or district means.
export const AT_LARGE = "At-Large";

// A holder the source named no name for. They still occupy the post, so the row must not
// read as vacant.
export const UNNAMED_HOLDER = "Unnamed";

const byName = (a: string, b: string) => a.localeCompare(b);

export const holderNames = (memberships: Membership[], postId: string): string[] =>
  memberships
    .filter((membership) => membership.post_id === postId)
    .map((membership) => membership.person_name ?? UNNAMED_HOLDER)
    .sort(byName);

/** Every post a jurisdiction has, grouped under its role, with holders attached. */
export function groupPostsByRole(posts: Post[], memberships: Membership[]): RoleGroup[] {
  const groups = new Map<string, PostRow[]>();

  for (const post of posts) {
    const names = holderNames(memberships, post.id);
    const rows = groups.get(post.role_id) ?? [];
    rows.push({
      ...post,
      holder_names: names,
      // Counted from the post's own holders, not the names: a person with no name still
      // occupies the post, and the anomaly is about capacity, not about rendering.
      over_headcount: post.holders > post.headcount,
    });
    groups.set(post.role_id, rows);
  }

  return [...groups.entries()].map(([role_id, rows]) => {
    // Every post in the group shares the role, so any row carries its label.
    const headcount = rows.reduce((total, row) => total + row.headcount, 0);
    const filled = rows.reduce((total, row) => total + row.holders, 0);
    return {
      role_id,
      role_label: rows[0].role_label,
      posts: rows,
      headcount,
      filled,
      free: Math.max(0, headcount - filled),
    };
  });
}


/** How a post's division reads as a row heading.
 *
 * Shares `parseDivision` with `divisionOcdidToFriendly` and differs only in rendering: that
 * one is a compact badge (`[W1]`) to sit beside a name and returns "" for a place. Here the
 * place case is the meaningful one — a post with no sub-division covers the whole
 * jurisdiction, which is what at-large means.
 */
export const divisionName = (division_ocdid: string): string => {
  const { key, value } = parseDivision(division_ocdid);
  if (!key || key === PLACE_LABEL) return AT_LARGE;
  const words = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return value ? `${words} ${value}` : words;
};

/** The identifier itself, shown beside the name so the ocdid stays visible. */
export const divisionKey = (division_ocdid: string): string => {
  const { key, value } = parseDivision(division_ocdid);
  return value ? `${key}:${value}` : key;
};


// The designations a person can add a post under. Closed on purpose: an ocdid built from a
// free-text designation is one nothing else in the system can match.
export const ADDABLE_DIVISIONS = ["at-large", "ward", "council_district"] as const;
export type AddableDivision = (typeof ADDABLE_DIVISIONS)[number];

export const AT_LARGE_DIVISION: AddableDivision = "at-large";

/** Build the division ocdid a new post sits on.
 *
 * At-large is the jurisdiction's own division — the same rule `division_ocdid` uses on the
 * parser side, where a label naming no area belongs to the whole jurisdiction.
 */
export function buildDivisionOcdid(
  jurisdictionOcdid: string,
  designation: AddableDivision,
  value: string,
): string {
  const base = jurisdictionToDivisionBase(jurisdictionOcdid);
  if (designation === AT_LARGE_DIVISION) return base;
  return `${base}/${designation}:${value.trim()}`;
}
