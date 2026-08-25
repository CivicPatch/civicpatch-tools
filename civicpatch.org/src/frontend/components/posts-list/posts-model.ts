import { PLACE_LABEL } from "../edit-people/person-edit-utils.js";
import { parseDivision } from "../ocdid-utils.js";
import { jurisdictionToDivisionBase } from "../edit-people/person-edit-utils.js";

export interface Post {
  id: string;
  role_id: string;
  division_ocdid: string;
  label: string | null;

  // Underscored: no civic standard defines these, so dropping every `_*` key leaves a
  // conforming Post.
  _headcount: number;
  _is_tracked: boolean;
  _is_verified: boolean;
}

export interface RoleOption {
  id: string;
  label: string;
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
      over_headcount: names.length > post._headcount,
    });
    groups.set(post.role_id, rows);
  }

  return [...groups.entries()].map(([role_id, rows]) => {
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

// Mirrors `_DIVISION_LABELS` in `membership_label.py`; a drift shows the same division two
// ways on one screen.
const DIVISION_LABELS: Record<string, string> = {
  ward: "Ward",
  council_district: "District",
  district: "District",
  precinct: "Precinct",
  subdistrict: "Subdistrict",
};

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
  designation: AddableDivision,
  value: string,
): string {
  const base = jurisdictionToDivisionBase(jurisdictionOcdid);
  if (designation === AT_LARGE_DIVISION) return base;
  return `${base}/${designation}:${value.trim()}`;
}

// Mirrors `_CARDINALS` in `label_parser.py`.
const CARDINALS = [
  "north",
  "south",
  "east",
  "west",
  "northeast",
  "northwest",
  "southeast",
  "southwest",
  "central",
] as const;

/** Mirrors `_is_value` in `label_parser.py`, and must stay the *same* closed set: a post whose
 * ocdid a scrape can never produce sits unverified forever with a duplicate beside it. */
export function isDivisionValue(value: string): boolean {
  const key = value.trim().toLowerCase();
  if (!key) return false;
  // Ordinals too: the parser normalises "3rd" to "3" before this test.
  if (/^\d+(st|nd|rd|th)?$/.test(key)) return true;
  if ((CARDINALS as readonly string[]).includes(key)) return true;
  return key.length === 1 && /[a-z]/.test(key);
}

/** The inverse of `buildDivisionOcdid`. A key we cannot offer reads as at-large rather than
 * becoming a blank select that saves something different from what it shows. */
export function divisionSelection(division_ocdid: string | null | undefined): {
  designation: AddableDivision;
  value: string;
} {
  const { key, value } = parseDivision(division_ocdid ?? "");
  const designation = ADDABLE_DIVISIONS.find((option) => option === key);
  return designation && designation !== AT_LARGE_DIVISION
    ? { designation, value }
    : { designation: AT_LARGE_DIVISION, value: "" };
}

export interface PostOption {
  post_id: string;
  role_id: string;
  role_label: string;
  division_ocdid: string;
  label: string;
  held: number;
  headcount: number;
  // Not disabled: a real body can seat an extra member, and refusing the truth is worse.
  full: boolean;
}

export function postOptions(
  posts: Post[],
  memberships: Membership[],
  roleLabels: Map<string, string>,
): PostOption[] {
  return posts.map((post) => {
    const roleLabel = roleLabels.get(post.role_id) ?? post.role_id;
    const held = holderNames(memberships, post.id).length;
    return {
      post_id: post.id,
      role_id: post.role_id,
      role_label: roleLabel,
      division_ocdid: post.division_ocdid,
      label: post.label ?? `${roleLabel}, ${divisionName(post.division_ocdid)}`,
      held,
      headcount: post._headcount,
      full: held >= post._headcount,
    };
  });
}

export function selectedPostId(
  options: PostOption[],
  roleId: string | null | undefined,
  divisionOcdid: string | null | undefined,
): string | null {
  const found = options.find(
    (option) =>
      option.role_id === roleId && option.division_ocdid === divisionOcdid,
  );
  return found?.post_id ?? null;
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

/** Lives here rather than beside the picker so it stays testable: importing a component pulls
 * in haunted, which the unit tests cannot resolve. */
export function byRole(options: PostOption[]): [string, PostOption[]][] {
  const groups = new Map<string, PostOption[]>();
  for (const option of options) {
    groups.set(option.role_label, [
      ...(groups.get(option.role_label) ?? []),
      option,
    ]);
  }
  return [...groups.entries()];
}

export interface OfficeOption {
  // A pick is a *post*, never a rewrite of what the source said: `labels` stay as scraped.
  post_id: string;
  text: string;
}

export const DERIVED_POST = "Derived from the labels";

/** A post is stored by id and never displayed as one — every path rendering the Post field
 * goes through here, so a UUID cannot reach a reader by being one path short. */
export function postLabelFor(
  post_id: unknown,
  options: OfficeOption[],
): string {
  if (!post_id) return DERIVED_POST;
  return (
    options.find((option) => option.post_id === post_id)?.text ?? DERIVED_POST
  );
}

/** One option per post. Two people on one post may have been named differently by the source,
 * but the post is the same — offering it twice asks a reviewer to choose between spellings. */
export function officeOptions(memberships: Membership[]): OfficeOption[] {
  const seen = new Map<string, OfficeOption>();
  for (const membership of memberships) {
    if (seen.has(membership.post_id)) continue;
    seen.set(membership.post_id, {
      post_id: membership.post_id,
      // The post alone, not the holder's own membership label.
      text: postName(membership),
    });
  }
  return [...seen.values()].sort((a, b) => a.text.localeCompare(b.text));
}

/** Each post's name, then what the source said beyond it: "Council Member, At-Large, Seat 3".
 *
 * Not `…Subtitle`: it is a row subtitle, an option label and a card line, and naming a value
 * after one of its slots is how one string ends up computed three ways.
 */
export function postsHeld(
  memberships: { post_label: string; label: string | null }[],
): string {
  return memberships
    .map((membership) =>
      [postName(membership), membership.label].filter(Boolean).join(", "),
    )
    .join("; ");
}

/** Singular where `memberships` is plural: every caller puts a person in one bucket, so the
 * first post is the pick. */
export function divisionOf(memberships: { division_ocdid: string }[]): string {
  return memberships[0]?.division_ocdid ?? "";
}

/** A real regrouping, not a re-sort: the post axis shows one person once per post, with no
 * hint the rows are the same human. */
export function groupMembershipsByPerson(
  memberships: Membership[],
): PersonRow[] {
  const groups = new Map<string, Membership[]>();
  for (const membership of memberships) {
    const name = membership.person_name ?? UNNAMED_HOLDER;
    groups.set(name, [...(groups.get(name) ?? []), membership]);
  }
  return [...groups.entries()].map(([person_name, posts]) => ({
    person_name,
    posts,
  }));
}

/** The seat itself, as the server rendered it — `core.membership_label.rendered_post_label`
 * names a post nobody named, so nothing here composes one.
 *
 * Not `membership.label`: that says what the source called this *person* beyond the post, so
 * using it here would replace "Deputy Mayor Pro Tempore" with the seat.
 */
export const postName = (membership: { post_label: string }): string =>
  membership.post_label;

/** Everything the parser made of a source label, in the order it decides them: designations
 * before roles (closed vocabulary, hardest to be wrong about), residue last. An at-large post
 * still lists its division — "no division" is a decision, not a gap. */
export function decompose(membership: Membership): ParsePart[] {
  return [
    { kind: PART_ROLE, value: membership.role_id },
    { kind: PART_DIVISION, value: divisionName(membership.division_ocdid) },
    ...membership.designations.map(
      (value) => ({ kind: PART_DESIGNATION, value }) as ParsePart,
    ),
    ...membership.unmatched_text.map(
      (value) => ({ kind: PART_UNMATCHED, value }) as ParsePart,
    ),
  ];
}
