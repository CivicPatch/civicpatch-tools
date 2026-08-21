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
  // Underscored: no civic standard defines these, so a consumer dropping every `_*` key is
  // left with a conforming Post. Stored ones are named that way in the schema; `_is_verified`
  // is computed and aliased in the query.
  _headcount: number;
  _is_tracked: boolean;
  _is_verified: boolean;
}

export interface Membership {
  post_id: string;
  person_name: string | null;
  role_id: string;
  division_ocdid: string;
  label: string | null;
  post_label: string | null;
  // The whole parse: what the source said, and what each piece of it became.
  source_labels: string[];
  designations: string[];
  unmatched_text: string[];
}

// What a piece of a source label was resolved to. Named because the renderer keys styling on
// them and the tests assert them — a bare string here could drift silently.
export const PART_ROLE = "role";
export const PART_DIVISION = "division";
export const PART_DESIGNATION = "designation";
export const PART_UNMATCHED = "unmatched";

export type PartKind =
  | typeof PART_ROLE
  | typeof PART_DIVISION
  | typeof PART_DESIGNATION
  | typeof PART_UNMATCHED;

export interface ParsePart {
  kind: PartKind;
  value: string;
}

export interface PersonRow {
  person_name: string;
  posts: Membership[];
}

export interface PostRow extends Post {
  // Occupancy, and the only source of it. Every membership yields a name here, real or
  // `UNNAMED_HOLDER`, so the length is the count — the server used to send one too, dated
  // separately, which could disagree with this list. One read, one answer.
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
export function groupPostsByRole(
  posts: Post[],
  memberships: Membership[],
  roleLabels: Map<string, string>,
): RoleGroup[] {
  const groups = new Map<string, PostRow[]>();

  for (const post of posts) {
    const names = holderNames(memberships, post.id);
    const rows = groups.get(post.role_id) ?? [];
    rows.push({
      ...post,
      holder_names: names,
      over_headcount: names.length > post._headcount,
    });
    groups.set(post.role_id, rows);
  }

  return [...groups.entries()].map(([role_id, rows]) => {
    // Every post in the group shares the role, so any row carries its label.
    const headcount = rows.reduce((total, row) => total + row._headcount, 0);
    const filled = rows.reduce(
      (total, row) => total + row.holder_names.length,
      0,
    );
    return {
      role_id,
      role_label: roleLabels.get(role_id) ?? role_id,
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


/** The same memberships, gathered under the person instead of the post.
 *
 * One person can hold posts in several bodies, so this is a real regrouping rather than a
 * re-sort — the post axis would show them once per post with no hint the rows are the same
 * human.
 */
export function groupMembershipsByPerson(memberships: Membership[]): PersonRow[] {
  const groups = new Map<string, Membership[]>();
  for (const membership of memberships) {
    const name = membership.person_name ?? UNNAMED_HOLDER;
    groups.set(name, [...(groups.get(name) ?? []), membership]);
  }
  return [...groups.entries()].map(([person_name, posts]) => ({ person_name, posts }));
}

/** What to call a post in a person's list: what someone named it, else role and division. */
export const postTitle = (membership: Membership): string =>
  membership.label ??
  membership.post_label ??
  `${membership.role_id} · ${divisionName(membership.division_ocdid)}`;


/** Everything the parser made of a person's source label, in the order it decides them.
 *
 * Designations run before roles in the parser because they are a closed vocabulary requiring
 * a value, so they are hardest to be wrong about; this mirrors that order rather than the
 * order the words appear. `unmatched` comes last because it is the residue — what nothing
 * else claimed.
 *
 * An at-large post still lists its division: "no area" is a decision the parser made, not a
 * gap, and hiding it would make the row look incompletely parsed.
 */
export function decompose(membership: Membership): ParsePart[] {
  return [
    { kind: PART_ROLE, value: membership.role_id },
    { kind: PART_DIVISION, value: divisionName(membership.division_ocdid) },
    ...membership.designations.map((value) => ({ kind: PART_DESIGNATION, value }) as ParsePart),
    ...membership.unmatched_text.map((value) => ({ kind: PART_UNMATCHED, value }) as ParsePart),
  ];
}
