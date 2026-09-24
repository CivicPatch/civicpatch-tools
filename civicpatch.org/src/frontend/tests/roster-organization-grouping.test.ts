import { describe, it, expect } from "vitest";
import { groupCardsByOrganization } from "../pages/jurisdictions-page/roster-organization-grouping.js";

const COUNCIL = "org-council";
const SCHOOLS = "org-schools";

const organizations = [
  { id: COUNCIL, name: "City Council", posts: [] },
  { id: SCHOOLS, name: "School Board", posts: [] },
] as any[];

// A row as `buildPersonCards` emits one: already about a single body, and carrying which.
const row = (personId: string, organizationId?: string) =>
  ({ personId, organizationId, oldRecord: null, newRecord: null }) as any;

const idsUnder = (groups: any[], organizationId: string) =>
  groups
    .find((group) => group.organization.id === organizationId)!
    .cards.map((c: any) => c.personId);

describe("groupCardsByOrganization", () => {
  // These used to verify that the grouping *placed* cards — resolving a held post back to its
  // organization, cloning the card per body, stamping a removed status. All of that moved into
  // `buildPersonCards` on 2026-09-24, where the review page gets it too; the tests for it live
  // in person-cards.test.ts. What is left here is the group-by.
  it("files a row under the body it is about", () => {
    const groups = groupCardsByOrganization(
      [row("p1", COUNCIL), row("p2", SCHOOLS)],
      organizations,
      new Map(),
    );

    expect(idsUnder(groups, COUNCIL)).toEqual(["p1"]);
    expect(idsUnder(groups, SCHOOLS)).toEqual(["p2"]);
  });

  it("shows somebody under every body they have a row for", () => {
    const groups = groupCardsByOrganization(
      [row("p1", COUNCIL), row("p1", SCHOOLS)],
      organizations,
      new Map(),
    );

    expect(idsUnder(groups, COUNCIL)).toEqual(["p1"]);
    expect(idsUnder(groups, SCHOOLS)).toEqual(["p1"]);
  });

  it("puts somebody with no body where Add was clicked", () => {
    const groups = groupCardsByOrganization(
      [row("new-1")],
      organizations,
      new Map([["new-1", SCHOOLS]]),
    );

    expect(idsUnder(groups, SCHOOLS)).toEqual(["new-1"]);
    expect(idsUnder(groups, COUNCIL)).toEqual([]);
  });

  it("falls back to the first body for somebody nobody has placed at all", () => {
    const groups = groupCardsByOrganization([row("p9")], organizations, new Map());

    expect(idsUnder(groups, COUNCIL)).toEqual(["p9"]);
    // And the row gets the body it landed in, so it keys and edits like any other.
    expect(
      groups.find((g) => g.organization.id === COUNCIL)!.cards[0].organizationId,
    ).toBe(COUNCIL);
  });

  it("drops a row whose body this jurisdiction does not list", () => {
    const groups = groupCardsByOrganization(
      [row("p1", "org-elsewhere")],
      organizations,
      new Map(),
    );

    expect(groups.flatMap((group) => group.cards)).toEqual([]);
  });
});
