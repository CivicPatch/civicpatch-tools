import { PLACE_LABEL } from "../edit-people/person-edit-utils.js";
import { parseDivision } from "../ocdid-utils.js";
import { jurisdictionToDivisionBase } from "../edit-people/person-edit-utils.js";
import { DIVISION_LABELS } from "../../utils/division-utils.js";

export interface Post {
  id: string;
  organization_id: string;
  role_id: string;
  division_ocdid: string;
  label: string;

  // `meta_`-marked: no civic standard defines these.
  meta_headcount: number;
  meta_is_tracked: boolean;
  meta_is_verified: boolean;
}

export interface RoleOption {
  id: string;
  label: string;
}

// A scrape's claim about a person's post, independent of whether any established post matches
// it yet — the office picker folds these into its own role/division options (see its own
// comment) so a proposal is always something a reviewer can select, not just describe.
export interface ProposedPost {
  role_id: string;
  role_label: string;
  division_ocdid: string;
}

export interface Membership {
  person_id: string;
  person_name: string | null;

  label: string | null;

  role_id: string;
  role_label: string;

  post_id: string;
  post_label: string;
  division_ocdid: string;

  source_labels: string[];
  designations: string[];
  unmatched_text: string[];
}

export interface PostRow extends Post {
  holder_names: string[];
  over_headcount: boolean;
}

export interface RoleGroup {
  role_id: string;
  role_label: string;
  posts: PostRow[];
  headcount: number;
  filled: number;

  // Floors at zero; over-subscription is per-post, and `over_headcount` carries it.
  free: number;
}

// What `place:` with no ward or district means — a domain state, not decoration.
export const AT_LARGE = "At-Large";

// They still occupy the post, so the row must not read as vacant.
export const UNNAMED_HOLDER = "Unnamed";

const byName = (a: string, b: string) => a.localeCompare(b);

export const holderNames = (
  memberships: Membership[],
  postId: string,
): string[] =>
  memberships
    .filter((membership) => membership.post_id === postId)
    .map((membership) => membership.person_name ?? UNNAMED_HOLDER)
    .sort(byName);

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
      over_headcount: names.length > post.meta_headcount,
    });
    groups.set(post.role_id, rows);
  }

  return [...groups.entries()].map(([role_id, rows]) => {
    const headcount = rows.reduce((total, row) => total + row.meta_headcount, 0);
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

export const divisionName = (division_ocdid: string): string => {
  const { key, value } = parseDivision(division_ocdid);
  if (!key || key === PLACE_LABEL) return AT_LARGE;
  const words =
    DIVISION_LABELS[key] ??
    key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return value ? `${words} ${value}` : words;
};

/** The identifier itself, shown beside the name so the ocdid stays visible. */
export const divisionKey = (division_ocdid: string): string => {
  const { key, value } = parseDivision(division_ocdid);
  return value ? `${key}:${value}` : key;
};

export const ADDABLE_DIVISIONS = [
  "at-large",
  "ward",
  "council_district",
] as const;
export type AddableDivision = (typeof ADDABLE_DIVISIONS)[number];

export const AT_LARGE_DIVISION: AddableDivision = "at-large";

export function buildDivisionOcdid(
  jurisdictionOcdid: string,
  divisionKind: AddableDivision,
  divisionValue: string,
): string {
  const base = jurisdictionToDivisionBase(jurisdictionOcdid);
  if (divisionKind === AT_LARGE_DIVISION) return base;
  return `${base}/${divisionKind}:${divisionValue.trim()}`;
}

/** The inverse of `buildDivisionOcdid`. A key we cannot offer reads as at-large rather than
 * becoming a blank select that saves something different from what it shows. */
export function divisionSelection(division_ocdid: string | null | undefined): {
  divisionKind: AddableDivision;
  divisionValue: string;
} {
  const { key, value } = parseDivision(division_ocdid ?? "");
  const divisionKind = ADDABLE_DIVISIONS.find((option) => option === key);
  return divisionKind && divisionKind !== AT_LARGE_DIVISION
    ? { divisionKind, divisionValue: value }
    : { divisionKind: AT_LARGE_DIVISION, divisionValue: "" };
}

/** The post the derivation chose for one person. `post_id` is null when no row holds it yet —
 * publishing mints it, so the picker offers it by label and says what accepting it does. */
export interface DerivedPost {
  post_id: string | null;
  label: string;
  // Absent from `heldPost`'s return — only `derivedPostFor` (editor-props.ts) attaches it,
  // since a membership label needs the full proposal or membership, not just its post.
  membershipLabel?: string | null;
  // A proposal's own identity — present exactly when `post_id` is null, since that's the one
  // case `civ-office-picker` can't pre-select by looking the post up in its own `posts` list:
  // there is no row yet to find. `heldPost` never sets these; an already-published post is
  // already in that list, `post_id` alone is enough to find it there.
  role_id?: string;
  division_ocdid?: string;
}

/** The post a person actually holds, which is a memberships question — `post_id` on a record is
 * the reviewer's pick and is null until they make one, so it cannot answer this.
 *
 * Only when they hold exactly one: two is no single answer, the same rule the picker follows. */
export function heldPost(
  memberships: { post_id: string; post_label: string }[] | null | undefined,
): DerivedPost | null {
  const held = memberships ?? [];
  if (held.length !== 1 || !held[0].post_id) return null;
  return { post_id: held[0].post_id, label: held[0].post_label };
}

/** The human label on the one post someone holds — what `memberships.assign` would send
 * back, as opposed to `heldPost`'s post-derived label. Same one-membership rule as `heldPost`. */
export function heldMembershipLabel(
  memberships: { post_id: string; label: string | null }[] | null | undefined,
): string | null {
  const held = memberships ?? [];
  if (held.length !== 1 || !held[0].post_id) return null;
  return held[0].label ?? null;
}

/** The backend's `derive_label` shape. At-large adds nothing — `_division_phrase` returns None
 * for it, so saying it here would promise a label the server would not produce. */
export function derivedPostLabel(
  roleLabel: string,
  division_ocdid: string,
): string {
  if (!roleLabel) return "";
  const division = divisionName(division_ocdid);
  return division === AT_LARGE ? roleLabel : `${roleLabel}, ${division}`;
}

/** A post is stored by id and never displayed as one — every path rendering the Post field
 * goes through here, so a UUID cannot reach a reader by being one path short. */
export function postLabelFor(post_id: unknown, posts: Post[]): string {
  return posts.find((post) => post.id === post_id)?.label ?? "";
}

/** Each post's name, then what the source said beyond it: "Council Member, At-Large, Seat 3".
 *
 * Not `…Subtitle`: it is a row subtitle, an option label and a card line, and naming a value
 * after one of its slots is how one string ends up computed three ways.
 *
 * `label` is only what the occupant's own labels added beyond the seat (`render` on the
 * backend no longer folds the post's own name in) — composed here for a caller with no
 * separate place to show the two. A caller that shows them apart (the card grid's two
 * lines, the review diff's two rows) reads `post_label`/`label` itself instead of this.
 */
export function postsHeld(
  memberships: { post_label: string; label: string | null }[],
): string {
  return memberships
    .map((membership) =>
      membership.label ? `${postName(membership)}, ${membership.label}` : postName(membership),
    )
    .join("; ");
}

/** Singular where `memberships` is plural: every caller puts a person in one bucket, so the
 * first post is the pick. */
export function divisionOf(memberships: { division_ocdid: string }[]): string {
  return memberships[0]?.division_ocdid ?? "";
}

/** The seat itself, as the server composed it. Not `membership.label`: that is what the source
 * called this *person* beyond the post. */
export const postName = (membership: { post_label: string }): string =>
  membership.post_label;
