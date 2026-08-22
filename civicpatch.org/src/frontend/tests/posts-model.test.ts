import { describe, it, expect } from "vitest";
import {
  groupPostsByRole,
  holderNames,
  divisionName,
  divisionKey,
  AT_LARGE,
  UNNAMED_HOLDER,
  buildDivisionOcdid,
  AT_LARGE_DIVISION,
  groupMembershipsByPerson,
  postTitle,
  decompose,
  PART_ROLE,
  PART_DIVISION,
  PART_DESIGNATION,
  PART_UNMATCHED,
} from "../components/posts-list/posts-model.js";
import type { Post, Membership } from "../components/posts-list/posts-model.js";

const post = (overrides: Partial<Post> & { id: string; role_id: string }): Post => ({
  division_ocdid: "ocd-division/country:us/state:wa/place:x",
  label: null,
  _headcount: 1,
  _is_verified: false,
  _is_tracked: true,
  ...overrides,
});

// Occupancy is read off the memberships now, not a count the server sends, so a test that
// wants N holders supplies N memberships.
const held = (postId: string, count: number) =>
  Array.from({ length: count }, (_, index) => ({
    post_id: postId,
    person_name: `Holder ${index}`,
  }));

const ROLE_LABELS = new Map([
  ["council-member", "Council Member"],
  ["mayor", "Mayor"],
  ["clerk", "Clerk"],
]);

describe("groupPostsByRole", () => {
  it("gathers a role's posts under one heading", () => {
    const groups = groupPostsByRole(
      [
        post({ id: "a", role_id: "council-member" }),
        post({ id: "b", role_id: "mayor" }),
        post({ id: "c", role_id: "council-member" }),
      ],
      [],
      ROLE_LABELS,
    );

    expect(groups.map((g) => g.role_id)).toEqual(["council-member", "mayor"]);
    expect(groups[0].posts.map((p) => p.id)).toEqual(["a", "c"]);
  });

  it("preserves the order the API returned", () => {
    // The posts read already sorts by role then division. Re-sorting here would fight it,
    // and the two would drift the first time either changed.
    const groups = groupPostsByRole(
      [post({ id: "z", role_id: "mayor" }), post({ id: "a", role_id: "council-member" })],
      [],
      ROLE_LABELS,
    );

    expect(groups.map((g) => g.role_id)).toEqual(["mayor", "council-member"]);
  });

  it("sums capacity across the role so the header can say how much is unfilled", () => {
    const groups = groupPostsByRole(
      [
        post({ id: "a", role_id: "council-member", _headcount: 7 }),
        post({ id: "b", role_id: "council-member", _headcount: 4 }),
      ],
      [...held("a", 5), ...held("b", 3)],
      ROLE_LABELS,
    );

    expect(groups[0]).toMatchObject({ headcount: 11, filled: 8, free: 3 });
  });

  it("floors free at zero, leaving the anomaly on the post that has it", () => {
    // An over-subscribed post is a real state — two people found on a one-person office —
    // but "-1 free" on the role heading reads as a counting bug rather than a data problem.
    const groups = groupPostsByRole(
      [post({ id: "a", role_id: "mayor", _headcount: 1 })],
      held("a", 2),
      ROLE_LABELS,
    );

    expect(groups[0].free).toBe(0);
    expect(groups[0].posts[0].over_headcount).toBe(true);
  });

  it("attaches holders by name, since the screen lists people not counts", () => {
    const groups = groupPostsByRole(
      [post({ id: "a", role_id: "mayor" })],
      [
        { post_id: "a", person_name: "Robert Michaud" },
        { post_id: "b", person_name: "Someone Else" },
        { post_id: "a", person_name: "Gilles Bergeron" },
      ],
      ROLE_LABELS,
    );

    expect(groups[0].posts[0].holder_names).toEqual(["Gilles Bergeron", "Robert Michaud"]);
  });

  it("keeps a nameless holder in the list", () => {
    // They still occupy the post. Dropping them would make the row read as vacant, which is
    // the one thing a roster screen must not get wrong.
    expect(holderNames([{ post_id: "a", person_name: null }], "a")).toEqual([UNNAMED_HOLDER]);
  });
});


describe("divisionName", () => {
  it("names a whole-jurisdiction post at-large", () => {
    // The case the badge helper returns "" for. Blank would read as missing data on a row
    // heading, when it is the most informative answer available.
    expect(divisionName("ocd-division/country:us/state:wa/place:berlin")).toBe(AT_LARGE);
  });

  it("reads a sub-division as words", () => {
    expect(divisionName("ocd-division/country:us/state:wa/place:x/ward:3")).toBe("Ward 3");
    expect(divisionName("ocd-division/country:us/state:wa/place:x/council_district:3")).toBe(
      "Council District 3",
    );
  });

  it("keeps the identifier visible beside the name", () => {
    expect(divisionKey("ocd-division/country:us/state:wa/place:x/ward:3")).toBe("ward:3");
  });
});


describe("buildDivisionOcdid", () => {
  const jurisdiction = "ocd-jurisdiction/country:us/state:wa/place:buckley/government";
  const base = "ocd-division/country:us/state:wa/place:buckley";

  it("puts an at-large post on the jurisdiction's own division", () => {
    // Same rule the parser uses: a label naming no division belongs to the whole jurisdiction.
    // Inventing an "at-large" segment would mint an ocdid nothing else can match.
    expect(buildDivisionOcdid(jurisdiction, AT_LARGE_DIVISION, "")).toBe(base);
  });

  it("appends a numbered division", () => {
    expect(buildDivisionOcdid(jurisdiction, "ward", "3")).toBe(`${base}/ward:3`);
    expect(buildDivisionOcdid(jurisdiction, "council_district", "7")).toBe(
      `${base}/council_district:7`,
    );
  });

  it("trims the value, so a stray space cannot fork a division", () => {
    expect(buildDivisionOcdid(jurisdiction, "ward", " 3 ")).toBe(`${base}/ward:3`);
  });
});


describe("groupMembershipsByPerson", () => {
  const membership = (overrides: Partial<Membership>): Membership => ({
    post_id: "p",
    person_name: "Andrew Theriault",
    role_id: "council-member",
    division_ocdid: "ocd-division/country:us/state:wa/place:x/ward:2",
    label: null,
    post_label: null,
    ...overrides,
  });

  it("gathers one person's posts across bodies under a single row", () => {
    // The point of the axis: the post view shows them twice with no hint it is one human.
    const rows = groupMembershipsByPerson([
      membership({ post_id: "a" }),
      membership({ post_id: "b", person_name: "Diana Pelchat" }),
      membership({ post_id: "c" }),
    ]);

    expect(rows.map((r) => r.person_name)).toEqual(["Andrew Theriault", "Diana Pelchat"]);
    expect(rows[0].posts.map((p) => p.post_id)).toEqual(["a", "c"]);
  });

  it("keeps a nameless holder rather than dropping them", () => {
    expect(groupMembershipsByPerson([membership({ person_name: null })])[0].person_name).toBe(
      UNNAMED_HOLDER,
    );
  });
});

describe("postTitle", () => {
  const base = {
    post_id: "p",
    person_name: "X",
    role_id: "council-member",
    division_ocdid: "ocd-division/country:us/state:wa/place:x/ward:2",
  };

  it("names the post, ignoring what the membership adds on top of it", () => {
    // `membership.label` is the source's words for what the post does not say — a demoted
    // office or a portfolio. It is not another name for the seat, so it must not be the title.
    expect(postTitle({ ...base, label: "Council Member, Place 6", post_label: "Post Label" })).toBe(
      "Post Label",
    );
    expect(postTitle({ ...base, label: null, post_label: "Post Label" })).toBe("Post Label");
  });

  it("falls back to role and division when nobody has named it", () => {
    expect(postTitle({ ...base, label: null, post_label: null })).toBe(
      "council-member · Ward 2",
    );
  });
});


describe("decompose", () => {
  const membership = (overrides: Partial<Membership> = {}): Membership => ({
    post_id: "p",
    person_name: "X",
    role_id: "council-member",
    division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:3",
    label: null,
    post_label: null,
    source_labels: ["Council Member District 3 (Central Seattle)"],
    designations: [],
    unmatched_text: ["Central Seattle"],
    ...overrides,
  });

  it("accounts for every piece of the label, residue included", () => {
    // The point of the row: a curator can see what the parser did and judge it, rather than
    // being shown only where the person landed.
    expect(decompose(membership())).toEqual([
      { kind: PART_ROLE, value: "council-member" },
      { kind: PART_DIVISION, value: "Council District 3" },
      { kind: PART_UNMATCHED, value: "Central Seattle" },
    ]);
  });

  it("lists designations before the residue", () => {
    const parts = decompose(
      membership({ designations: ["Position 8"], unmatched_text: ["Citywide"] }),
    );

    expect(parts.map((p) => p.kind)).toEqual([
      PART_ROLE,
      PART_DIVISION,
      PART_DESIGNATION,
      PART_UNMATCHED,
    ]);
  });

  it("still shows the division for an at-large post", () => {
    // "No division" is a decision the parser made, not a gap. Omitting it would make a correctly
    // parsed at-large row look half-parsed.
    const parts = decompose(
      membership({
        division_ocdid: "ocd-division/country:us/state:wa/place:x",
        unmatched_text: [],
      }),
    );

    expect(parts).toContainEqual({ kind: PART_DIVISION, value: "At-Large" });
  });
});
