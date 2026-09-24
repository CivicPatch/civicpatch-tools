import { describe, it, expect } from "vitest";
import { groupCardsByOrganization } from "../pages/jurisdictions-page/roster-organization-grouping.js";
import { cardKey } from "../components/people/person-cards.js";

const COUNCIL = "org-council";
const SCHOOLS = "org-schools";
const MAYOR = "post-mayor";
const TRUSTEE = "post-trustee";

const organizations = [
  { id: COUNCIL, name: "City Council", posts: [{ id: MAYOR }] },
  { id: SCHOOLS, name: "School Board", posts: [{ id: TRUSTEE }] },
] as any[];

const card = (personId: string, postIds: string[]) =>
  ({
    personId,
    oldRecord: { id: personId, memberships: postIds.map((post_id) => ({ post_id })) },
    newRecord: null,
  }) as any;

const idsUnder = (groups: any[], organizationId: string) =>
  groups
    .find((group) => group.organization.id === organizationId)!
    .cards.map((c: any) => c.personId);

describe("groupCardsByOrganization", () => {
  it("files somebody under the body their office is in", () => {
    const groups = groupCardsByOrganization([card("p1", [MAYOR])], organizations, new Map());

    expect(idsUnder(groups, COUNCIL)).toEqual(["p1"]);
    expect(idsUnder(groups, SCHOOLS)).toEqual([]);
  });

  it("shows somebody under every body they hold an office in", () => {
    // Until 2026-09-23 this answered with one body and gave up on two, so a person on the
    // council and the school board was filed silently under whichever came first.
    const groups = groupCardsByOrganization(
      [card("p1", [MAYOR, TRUSTEE])],
      organizations,
      new Map(),
    );

    expect(idsUnder(groups, COUNCIL)).toEqual(["p1"]);
    expect(idsUnder(groups, SCHOOLS)).toEqual(["p1"]);
  });

  it("puts somebody who holds nothing where Add was clicked", () => {
    const groups = groupCardsByOrganization(
      [card("new-1", [])],
      organizations,
      new Map([["new-1", SCHOOLS]]),
    );

    expect(idsUnder(groups, SCHOOLS)).toEqual(["new-1"]);
    expect(idsUnder(groups, COUNCIL)).toEqual([]);
  });

  it("falls back to the first body for somebody nobody has placed", () => {
    const groups = groupCardsByOrganization([card("p9", [])], organizations, new Map());

    expect(idsUnder(groups, COUNCIL)).toEqual(["p9"]);
  });

  it("ignores an office in a body this jurisdiction does not list", () => {
    const groups = groupCardsByOrganization(
      [card("p1", ["post-elsewhere"])],
      organizations,
      new Map(),
    );

    // No body to file them under, so they land in the fallback rather than vanishing.
    expect(idsUnder(groups, COUNCIL)).toEqual(["p1"]);
  });

  it("gives each row the body it is about, so they are separate cards", () => {
    // The office, its label and its removal belong to the row. Sharing one card object would
    // mean removing them from the council struck them through on the school board too.
    const groups = groupCardsByOrganization(
      [card("p1", [MAYOR, TRUSTEE])],
      organizations,
      new Map(),
    );

    const council = groups.find((g) => g.organization.id === COUNCIL)!.cards[0];
    const schools = groups.find((g) => g.organization.id === SCHOOLS)!.cards[0];

    expect(council.organizationId).toBe(COUNCIL);
    expect(schools.organizationId).toBe(SCHOOLS);
    expect(council).not.toBe(schools);
    expect(cardKey(council)).not.toEqual(cardKey(schools));
  });
});
