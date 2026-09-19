import { describe, it, expect } from "vitest";
import {
  roleRank,
  sortByRoleRank,
  computeLeadIds,
  groupByRole,
} from "../components/people/person-card-grid-model.js";

const ROLE_ORDER = ["mayor", "council-president", "council-member", "clerk"];

const member = (roleId: string) => ({
  role_id: roleId,
  role_label: roleId,
  post_label: "",
  membership_label: null as string | null,
});

describe("roleRank", () => {
  it("is the lowest index among a person's roles", () => {
    const memberships = [member("clerk"), member("council-president")];
    expect(roleRank(memberships, ROLE_ORDER)).toBe(1);
  });

  it("is +Infinity for someone with no memberships", () => {
    expect(roleRank(undefined, ROLE_ORDER)).toBe(Number.POSITIVE_INFINITY);
  });

  it("ignores a role_id absent from roleOrder rather than crashing", () => {
    const memberships = [member("some-deactivated-role")];
    expect(roleRank(memberships, ROLE_ORDER)).toBe(Number.POSITIVE_INFINITY);
  });
});

describe("sortByRoleRank", () => {
  it("orders by rank and keeps ties in their original order", () => {
    const people = [
      { id: "a", memberships: [member("council-member")] },
      { id: "b", memberships: [member("mayor")] },
      { id: "c", memberships: [member("council-member")] },
      { id: "d", memberships: [member("council-president")] },
    ];
    expect(sortByRoleRank(people, ROLE_ORDER).map((p) => p.id)).toEqual([
      "b",
      "d",
      "a",
      "c",
    ]);
  });

  it("does not mutate the input array", () => {
    const people = [
      { id: "a", memberships: [member("clerk")] },
      { id: "b", memberships: [member("mayor")] },
    ];
    const copy = [...people];
    sortByRoleRank(people, ROLE_ORDER);
    expect(people).toEqual(copy);
  });
});

describe("computeLeadIds", () => {
  it("marks roles that outrank the page's plurality role", () => {
    const people = [
      { id: "mayor-1", memberships: [member("mayor")] },
      { id: "cm-1", memberships: [member("council-member")] },
      { id: "cm-2", memberships: [member("council-member")] },
      { id: "cm-3", memberships: [member("council-member")] },
    ];
    // council-member is the plurality (3 of 4); mayor outranks it, so only mayor is lead.
    expect(computeLeadIds(people, ROLE_ORDER)).toEqual(new Set(["mayor-1"]));
  });

  it("marks nobody when every role ties the plurality", () => {
    const people = [
      { id: "a", memberships: [member("council-member")] },
      { id: "b", memberships: [member("council-member")] },
    ];
    expect(computeLeadIds(people, ROLE_ORDER).size).toBe(0);
  });

  it("marks nobody on an empty page", () => {
    expect(computeLeadIds([], ROLE_ORDER).size).toBe(0);
  });
});

describe("groupByRole", () => {
  const seated = (
    id: string,
    roleId: string,
    postLabel: string,
    membershipLabel: string | null = null,
  ) => ({
    id,
    memberships: [{ ...member(roleId), post_label: postLabel, membership_label: membershipLabel }],
  });
  const idsIn = (people: ReturnType<typeof seated>[]) =>
    groupByRole(people, ROLE_ORDER).map((group) => group.people.map((person) => person.id));

  it("orders role groups, then post label, then the membership's own label", () => {
    const people = [
      seated("strauss", "council-member", "Council Member, District 6"),
      seated("foster", "council-member", "Council Member, Position 9"),
      seated("saka-pro-tem", "council-member", "Council Member, District 1", "Mayor Pro Tem"),
      seated("wilson", "mayor", "Mayor"),
      seated("saka", "council-member", "Council Member, District 1"),
    ];
    expect(idsIn(people)).toEqual([
      ["wilson"],
      ["saka", "saka-pro-tem", "strauss", "foster"],
    ]);
  });

  it("reads District 2 before District 10", () => {
    const people = [
      seated("ten", "council-member", "Council Member, District 10"),
      seated("two", "council-member", "Council Member, District 2"),
    ];
    expect(idsIn(people)).toEqual([["two", "ten"]]);
  });

  it("keeps arrival order when every label ties", () => {
    const people = [
      seated("b", "council-member", "Council Member, At Large"),
      seated("a", "council-member", "Council Member, At Large"),
    ];
    expect(idsIn(people)).toEqual([["b", "a"]]);
  });
});
