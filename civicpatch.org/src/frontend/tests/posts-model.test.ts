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
} from "../components/posts-list/posts-model.js";
import type { Post, Membership } from "../components/posts-list/posts-model.js";

const post = (overrides: Partial<Post> & { id: string; role_id: string }): Post => ({
  division_ocdid: "ocd-division/country:us/state:wa/place:x",
  label: null,
  headcount: 1,
  holders: 0,
  role_label: "Council Member",
  _verified: false,
  ...overrides,
});

describe("groupPostsByRole", () => {
  it("gathers a role's posts under one heading", () => {
    const groups = groupPostsByRole(
      [
        post({ id: "a", role_id: "council-member" }),
        post({ id: "b", role_id: "mayor" }),
        post({ id: "c", role_id: "council-member" }),
      ],
      [],
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
    );

    expect(groups.map((g) => g.role_id)).toEqual(["mayor", "council-member"]);
  });

  it("sums capacity across the role so the header can say how much is unfilled", () => {
    const groups = groupPostsByRole(
      [
        post({ id: "a", role_id: "council-member", headcount: 7, holders: 5 }),
        post({ id: "b", role_id: "council-member", headcount: 4, holders: 3 }),
      ],
      [],
    );

    expect(groups[0]).toMatchObject({ headcount: 11, filled: 8, free: 3 });
  });

  it("floors free at zero, leaving the anomaly on the post that has it", () => {
    // An over-subscribed post is a real state — two people found on a one-person office —
    // but "-1 free" on the role heading reads as a counting bug rather than a data problem.
    const groups = groupPostsByRole(
      [post({ id: "a", role_id: "mayor", headcount: 1, holders: 2 })],
      [],
    );

    expect(groups[0].free).toBe(0);
    expect(groups[0].posts[0].over_headcount).toBe(true);
  });

  it("attaches holders by name, since the screen lists people not counts", () => {
    const groups = groupPostsByRole(
      [post({ id: "a", role_id: "mayor", holders: 2 })],
      [
        { post_id: "a", person_name: "Robert Michaud" },
        { post_id: "b", person_name: "Someone Else" },
        { post_id: "a", person_name: "Gilles Bergeron" },
      ],
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
    // Same rule the parser uses: a label naming no area belongs to the whole jurisdiction.
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
