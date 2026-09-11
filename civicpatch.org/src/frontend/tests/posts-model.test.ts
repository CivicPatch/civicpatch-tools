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
  postName,
  divisionSelection,
  isDivisionValue,
  postsHeld,
  derivedPostLabel,
} from "../components/posts-list/posts-model.js";
import type { Post } from "../components/posts-list/posts-model.js";

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
