import { describe, it, expect } from "vitest";
import {
  roleRank,
  sortByRoleRank,
  computeLeadIds,
} from "../components/people/person-card-grid-model.js";

const ROLE_ORDER = ["mayor", "council-president", "council-member", "clerk"];

const member = (roleId: string) => ({
  post_id: "p1",
  role_id: roleId,
  role_label: roleId,
  division_ocdid: "",
  label: null,
  post_label: "",
  source_labels: [],
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
