import { describe, it, expect } from "vitest";
// @ts-expect-error — people-state-utils.js is plain JS without type declarations
import { buildPeoplePatch, changedFieldKeys, listChanged } from "../components/edit-people/hooks/people-state-utils.js";

const changes = (entries: [string, string[]][]) => new Map(entries);
const deleted = (...ids: string[]) => new Set(ids);

describe("changedFieldKeys", () => {
  it("names only the fields that differ from the baseline", () => {
    const original = { id: "a", name: "Alice", phones: ["x"] };
    const person = { id: "a", name: "Alice", phones: ["y"] };
    expect(changedFieldKeys(person, original)).toEqual(["phones"]);
  });

  it("compares by value, not identity", () => {
    const person = { id: "a", office: { name: "Mayor" } };
    const original = { id: "a", office: { name: "Mayor" } };
    expect(changedFieldKeys(person, original)).toEqual([]);
  });

  it("names the id when a person is re-identified", () => {
    expect(changedFieldKeys({ id: "canonical" }, { id: "scraped" })).toEqual(["id"]);
  });

  it("treats a person with no baseline as wholly changed", () => {
    expect(changedFieldKeys({ id: "new1", name: "Bob" }, undefined)).toEqual(["id", "name"]);
  });
});

describe("listChanged", () => {
  const a = { id: "a" };
  const b = { id: "b" };
  const c = { id: "c" };

  it("is false when the same rows stand in the same order", () => {
    expect(listChanged([a, b], [a, b])).toBe(false);
  });

  it("is true when rows are reordered", () => {
    expect(listChanged([b, a], [a, b])).toBe(true);
  });

  it("is true when a baseline row is gone (a merge collapsed it)", () => {
    expect(listChanged([a], [a, b])).toBe(true);
  });

  it("is false when a row is added — an added row has no baseline to reorder", () => {
    expect(listChanged([c, a, b], [a, b])).toBe(false);
  });
});

describe("buildPeoplePatch", () => {
  it("sends only the changed fields for an edited existing person", () => {
    const people = [{ id: "a", name: "Alice", phones: ["x"] }];
    expect(buildPeoplePatch(people, changes([["a", ["phones"]]]), deleted())).toEqual([
      { id: "a", fields: { phones: ["x"] } },
    ]);
  });

  it("sends empty fields for an untouched person", () => {
    expect(buildPeoplePatch([{ id: "a", name: "Alice" }], changes([["a", []]]), deleted())).toEqual([
      { id: "a", fields: {} },
    ]);
  });

  it("sends the whole entry for a new person", () => {
    const person = { id: "new1", name: "Bob", phones: [], _isNew: true };
    expect(buildPeoplePatch([person], changes([["new1", []]]), deleted())).toEqual([
      { id: "new1", fields: { id: "new1", name: "Bob", phones: [] } },
    ]);
  });

  it("sends the whole entry when the id changed (re-id)", () => {
    const person = { id: "canonical", name: "Bob" };
    expect(buildPeoplePatch([person], changes([["canonical", ["id", "name"]]]), deleted())).toEqual([
      { id: "canonical", fields: { id: "canonical", name: "Bob" } },
    ]);
  });

  it("omits deleted people (the backend reads omission as a deletion)", () => {
    const people = [{ id: "a" }, { id: "b" }];
    expect(
      buildPeoplePatch(people, changes([["a", []], ["b", []]]), deleted("b")).map((p: { id: string }) => p.id)
    ).toEqual(["a"]);
  });

  it("preserves order", () => {
    const people = [{ id: "c" }, { id: "a" }, { id: "b" }];
    expect(
      buildPeoplePatch(people, changes([["c", []], ["a", []], ["b", []]]), deleted()).map((p: { id: string }) => p.id)
    ).toEqual(["c", "a", "b"]);
  });
});
