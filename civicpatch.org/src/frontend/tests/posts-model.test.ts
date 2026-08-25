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
  postName,
  decompose,
  PART_ROLE,
  PART_DIVISION,
  PART_DESIGNATION,
  PART_UNMATCHED,
  postOptions,
  selectedPostId,
  byRole,
  divisionSelection,
  isDivisionValue,
  officeOptions,
  postsHeld,
  derivedPostLabel,
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
      "District 3",
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

describe("postName", () => {
  const base = {
    post_id: "p",
    person_name: "X",
    role_id: "council-member",
    division_ocdid: "ocd-division/country:us/state:wa/place:x/ward:2",
  };

  it("names the post, ignoring what the membership adds on top of it", () => {
    // `membership.label` is the source's words for what the post does not say — a demoted
    // office or a portfolio. It is not another name for the seat, so it must not be the title.
    expect(postName({ ...base, label: "Council Member, Place 6", post_label: "Post Label" })).toBe(
      "Post Label",
    );
    expect(postName({ ...base, label: null, post_label: "Post Label" })).toBe("Post Label");
  });

  it("reads the label the server rendered, composing nothing", () => {
    // A post nobody named is named by `core.membership_label.rendered_post_label` before it
    // reaches here. Composing a fallback client-side is what leaked "council-member, Ward 2" —
    // a role slug — into the UI, because this path never had the role's label to use.
    expect(postName({ ...base, label: null, post_label: "Council Member, Ward 2" })).toBe(
      "Council Member, Ward 2",
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
      { kind: PART_DIVISION, value: "District 3" },
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

describe("postOptions", () => {
  it("names an unnamed post by role and division", () => {
    const [option] = postOptions(
      [post({ id: "a", role_id: "council-member", division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:1" })],
      [],
      ROLE_LABELS,
    );
    expect(option.label).toBe("Council Member, District 1");
  });

  it("prefers the name a person gave the post", () => {
    const [option] = postOptions(
      [post({ id: "a", role_id: "council-member", label: "Position 8" })],
      [],
      ROLE_LABELS,
    );
    expect(option.label).toBe("Position 8");
  });

  it("counts holders and flags a post already at headcount", () => {
    const [full] = postOptions(
      [post({ id: "a", role_id: "council-member", _headcount: 2 })],
      held("a", 2) as never,
      ROLE_LABELS,
    );
    expect(full.held).toBe(2);
    expect(full.full).toBe(true);

    const [room] = postOptions(
      [post({ id: "a", role_id: "council-member", _headcount: 3 })],
      held("a", 2) as never,
      ROLE_LABELS,
    );
    expect(room.full).toBe(false);
  });

  it("falls back to the role id when the role is unknown", () => {
    const [option] = postOptions([post({ id: "a", role_id: "dogcatcher" })], [], ROLE_LABELS);
    expect(option.role_label).toBe("dogcatcher");
  });
});

describe("selectedPostId", () => {
  const options = postOptions(
    [
      post({ id: "p1", role_id: "council-member", division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:1" }),
      post({ id: "p2", role_id: "council-president", division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:3" }),
    ],
    [],
    ROLE_LABELS,
  );

  it("matches on the post key, not on the name", () =>
    expect(selectedPostId(options, "council-president", "ocd-division/country:us/state:wa/place:x/council_district:3")).toBe("p2"));

  it("returns null when the person is in no post we know", () =>
    expect(selectedPostId(options, "mayor", "ocd-division/country:us/state:wa/place:x")).toBeNull());

  it("does not match a right role in the wrong division", () =>
    expect(selectedPostId(options, "council-member", "ocd-division/country:us/state:wa/place:x/council_district:9")).toBeNull());
});

describe("byRole", () => {
  const options = postOptions(
    [
      post({ id: "a", role_id: "council-member", division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:1" }),
      post({ id: "b", role_id: "mayor" }),
      post({ id: "c", role_id: "council-member", division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:2" }),
    ],
    [],
    ROLE_LABELS,
  );

  it("gathers a role's posts under one heading even when they are not adjacent", () => {
    const groups = byRole(options);
    expect(groups.map(([label]) => label)).toEqual(["Council Member", "Mayor"]);
    expect(groups[0][1].map((option) => option.post_id)).toEqual(["a", "c"]);
  });

  it("keeps the roster's order rather than sorting", () =>
    expect(byRole(options)[0][0]).toBe("Council Member"));
});

describe("divisionSelection", () => {
  it("round-trips what buildDivisionOcdid produced", () => {
    for (const [designation, value] of [["ward", "3"], ["council_district", "7"]] as const) {
      const ocdid = buildDivisionOcdid("ocd-jurisdiction/country:us/state:wa/place:x/government", designation, value);
      expect(divisionSelection(ocdid)).toEqual({ designation, value });
    }
  });

  it("reads the jurisdiction's own division as at-large", () =>
    expect(divisionSelection("ocd-division/country:us/state:wa/place:x")).toEqual({
      designation: AT_LARGE_DIVISION,
      value: "",
    }));

  it("falls back to at-large for a designation the form cannot offer", () => {
    // Otherwise the select renders blank and Save writes something the form never showed.
    expect(divisionSelection("ocd-division/country:us/state:wa/place:x/precinct:4")).toEqual({
      designation: AT_LARGE_DIVISION,
      value: "",
    });
  });

  it("treats a missing division as at-large rather than throwing", () =>
    expect(divisionSelection(null).designation).toBe(AT_LARGE_DIVISION));
});

describe("isDivisionValue", () => {
  it("accepts the three closed sets the parser accepts", () => {
    for (const value of ["3", "12", "3rd", "North", "southeast", "A", "b"]) {
      expect(isDivisionValue(value), value).toBe(true);
    }
  });

  it("rejects a value carrying whitespace, which is never one token", () => {
    // The inputs strip whitespace as you type; this is the rule that stripping exists for.
    expect(isDivisionValue("Ward 3")).toBe(false);
    expect(isDivisionValue("North West")).toBe(false);
    // A stray trailing space is not a second token, so it is trimmed rather than refused.
    expect(isDivisionValue("3 ")).toBe(true);
  });

  it("rejects anything that would build an id no scrape can produce", () => {
    // "District Attorney" is the case that made the parser's set closed in the first place —
    // accepting it published `district:attorney` as a division for a county prosecutor.
    for (const value of ["", "  ", "Attorney", "North Side", "3B", "downtown"]) {
      expect(isDivisionValue(value), value).toBe(false);
    }
  });
});

describe("officeOptions", () => {
  const held = (over: Partial<Membership>): Membership => ({
    person_id: "p", post_id: "a", person_name: "A", role_id: "council-member",
    division_ocdid: "ocd-division/country:us/state:wa/place:x/ward:2", label: null, post_label: null,
    source_labels: ["Councilmember Ward 2"], designations: [], unmatched_text: [],
    ...over,
  });

  it("writes what the source said, so publish re-parses back to the same post", () => {
    // NOT the role's canonical label — that reproduces office.name for only 78% of people.
    const [option] = officeOptions([held({})]);
    expect(option.post_id).toBe("a");
  });

  it("names an option by the post alone, not by whoever holds it", () => {
    // `postsHeld` appends the holder's own membership label. An option is a post someone else
    // happens to sit in, so borrowing their title would offer "Deputy Mayor Pro Tempore" to a
    // reviewer picking a plain council seat.
    const [titled] = officeOptions([
      held({ post_label: "Council Member, Ward 2", label: "Deputy Mayor Pro Tempore" }),
    ]);
    expect(titled.text).toBe("Council Member, Ward 2");
  });

  it("offers one option per post, however many ways the source named it", () => {
    // Two spellings of one post are two annotations, not two choices.
    const options = officeOptions([
      held({ source_labels: ["Councilmember Ward 2"] }),
      held({ person_id: "q", source_labels: ["Council Member District 2"] }),
    ]);
    expect(options).toHaveLength(1);
  });

  it("offers a post even when the source never labelled the membership", () =>
    // The post exists either way; only the annotation is missing.
    expect(officeOptions([held({ source_labels: [] })])).toHaveLength(1));
});

describe("postsHeld", () => {
  const held = (over = {}) => ({
    post_label: null as string | null,
    label: null as string | null,
    role_id: "council-member",
    division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:5",
    ...over,
  });

  it("names the post once, never the division a second time", () => {
    // The bug this replaces read "Council Member District 5 - Councilmember District 5, [D5]":
    // two spellings we joined, plus the district again as a badge.
    expect(postsHeld([held({ post_label: "Council Member, District 5" })])).toBe(
      "Council Member, District 5",
    );
  });

  it("adds the membership label after the post label", () =>
    expect(
      postsHeld([
        held({ post_label: "Council Member, At-Large", label: "Seat 3" }),
      ]),
    ).toBe("Council Member, At-Large, Seat 3"));

  it("takes the post label as given, never rebuilding it", () =>
    // Every payload carries `post_label` rendered by `derive_label`, including for a post
    // nobody named. Rebuilding it here is the duplication this removed.
    expect(postsHeld([held({ post_label: "Council Member, District 5" })])).toBe(
      "Council Member, District 5",
    ));

  it("says nothing for someone holding no post", () =>
    expect(postsHeld([])).toBe(""));

  it("separates two posts, because a person can hold more than one", () =>
    expect(
      postsHeld([
        held({ post_label: "Council Member, District 5" }),
        held({ post_label: "Chair, Parks Board" }),
      ]),
    ).toBe("Council Member, District 5; Chair, Parks Board"));
});

describe("derivedPostLabel", () => {
  it("names a post by role and division, the way the server would", () =>
    expect(derivedPostLabel("Council Member", "ocd-division/country:us/state:wa/place:x/council_district:5")).toBe(
      "Council Member, District 5",
    ));

  it("adds nothing for at-large, because the server adds nothing either", () =>
    // `_division_phrase` returns None for a whole-government division. Saying "At-Large" here
    // would promise a label `derive_label` never produces.
    expect(derivedPostLabel("Mayor", "ocd-division/country:us/state:wa/place:x")).toBe("Mayor"));

  it("is empty until a role is chosen", () =>
    expect(derivedPostLabel("", "ocd-division/country:us/state:wa/place:x/ward:2")).toBe(""));
});
