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

// A role the add form can file a post under. The posts screen already fetches roles to label
// its groups; this is the same list kept as options rather than reduced to a lookup.
export interface RoleOption {
  id: string;
  label: string;
}

export interface Membership {
  // Carried so the by-person view can assign without a second lookup. The read has always
  // returned it; only this type left it out.
  person_id: string;
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
 * parser side, where a label naming no division belongs to the whole jurisdiction.
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




// The cardinal directions a division can be named for, mirroring `_CARDINALS` in
// `label_parser.py`. Wards and districts are named by direction as often as by number.
const CARDINALS = [
  "north", "south", "east", "west",
  "northeast", "northwest", "southeast", "southwest", "central",
] as const;

/** Whether a typed division value is one the parser would also produce.
 *
 * Mirrors `_is_value` in `label_parser.py`: a number, a cardinal direction, or a single
 * letter. Deliberately closed on both sides, and it has to stay the *same* closed set — a
 * hand-made post whose ocdid a scrape can never produce is a post nothing will ever match, so
 * it sits unverified forever and the roster quietly grows a duplicate beside it.
 */
export function isDivisionValue(value: string): boolean {
  const key = value.trim().toLowerCase();
  if (!key) return false;
  // Ordinals too: the parser normalises "3rd" to "3" before this test.
  if (/^\d+(st|nd|rd|th)?$/.test(key)) return true;
  if ((CARDINALS as readonly string[]).includes(key)) return true;
  return key.length === 1 && /[a-z]/.test(key);
}


/** The inverse of `buildDivisionOcdid`: which selector state shows this division.
 *
 * Anything outside the addable set reads as at-large, because at-large *is* "no sub-division"
 * — the jurisdiction's own division. A key we cannot offer would otherwise silently become a
 * blank select that saves something different from what it shows.
 */
export function divisionSelection(
  division_ocdid: string | null | undefined,
): { designation: AddableDivision; value: string } {
  const { key, value } = parseDivision(division_ocdid ?? "");
  const designation = ADDABLE_DIVISIONS.find((option) => option === key);
  return designation && designation !== AT_LARGE_DIVISION
    ? { designation, value }
    : { designation: AT_LARGE_DIVISION, value: "" };
}


// One choosable post. Flat rather than grouped: a <select> needs a flat option list, and the
// role is carried on each option so the renderer can group without a second structure.
export interface PostOption {
  post_id: string;
  role_id: string;
  role_label: string;
  division_ocdid: string;
  // What the option reads as. The post's own name when someone gave it one, else role and
  // division — the same precedence `postTitle` uses, so the picker and the roster agree.
  label: string;
  held: number;
  headcount: number;
  // Choosing this post would exceed its headcount. Not disabled: a real body can seat an extra
  // member, and refusing the truth is worse than showing it.
  full: boolean;
}

/** Every post a person could be put in, in the order the roster shows them. */
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

/** Which option a person is currently in, matched on the post's identity rather than its name.
 *
 * `(role_id, division_ocdid)` is the post key — the same pair the derivation matches on. Names
 * are what the picker replaces, so matching on one would reintroduce the problem.
 */
export function selectedPostId(
  options: PostOption[],
  roleId: string | null | undefined,
  divisionOcdid: string | null | undefined,
): string | null {
  const found = options.find(
    (option) => option.role_id === roleId && option.division_ocdid === divisionOcdid,
  );
  return found?.post_id ?? null;
}

/** Post options under their role, in the order the roster shows them.
 *
 * Lives here rather than beside the picker so it stays testable: importing a component pulls
 * in haunted, which the unit tests cannot resolve.
 */
export function byRole(options: PostOption[]): [string, PostOption[]][] {
  const groups = new Map<string, PostOption[]>();
  for (const option of options) {
    groups.set(option.role_label, [...(groups.get(option.role_label) ?? []), option]);
  }
  return [...groups.entries()];
}


// An office a reviewer can pick, drawn from what the jurisdiction already has. The editor
// writes `office.name` as text that publish re-parses, so the value written has to be text
// that resolves back to this same post — which is exactly what the source said.
export interface OfficeOption {
  // What to write. `source_labels` joined the way `office_name_to_labels` splits them, so the
  // publish parser lands on the post this option came from. NOT the role's canonical label:
  // measured against prod that reproduces `office.name` for only 78% of people.
  name: string;
  division_ocdid: string;
  // What to show: the post, and the membership label when the source said more than the post
  // does. "Council Member, Ward 3 — Deputy Mayor Pro Tempore".
  text: string;
}

const OFFICE_LABEL_SEPARATOR = " — ";

/** The distinct offices this jurisdiction's memberships describe.
 *
 * Deduplicated on what would be written, not on the post: two holders of one post can have
 * been named differently by the source, and those are genuinely two options.
 */
export function officeOptions(memberships: Membership[]): OfficeOption[] {
  const seen = new Map<string, OfficeOption>();
  for (const membership of memberships) {
    const name = membership.source_labels.join(" - ");
    if (!name) continue;
    const key = `${name}|${membership.division_ocdid}`;
    if (seen.has(key)) continue;
    const post = postTitle(membership);
    seen.set(key, {
      name,
      division_ocdid: membership.division_ocdid,
      text: membership.label ? `${post}${OFFICE_LABEL_SEPARATOR}${membership.label}` : post,
    });
  }
  return [...seen.values()].sort((a, b) => a.text.localeCompare(b.text));
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

/** The seat itself: what the post is called, else role and division.
 *
 * Not `membership.label` — that says what the source called this person *beyond* the post, so
 * using it here would replace "Deputy Mayor Pro Tempore" with "Council Member, At-Large, Place 6".
 */
export const postTitle = (membership: Membership): string =>
  membership.post_label ??
  `${membership.role_id}, ${divisionName(membership.division_ocdid)}`;


/** Everything the parser made of a person's source label, in the order it decides them.
 *
 * Designations run before roles in the parser because they are a closed vocabulary requiring
 * a value, so they are hardest to be wrong about; this mirrors that order rather than the
 * order the words appear. `unmatched` comes last because it is the residue — what nothing
 * else claimed.
 *
 * An at-large post still lists its division: "no division" is a decision the parser made, not a
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
