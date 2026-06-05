import { describe, it, expect } from "vitest";
// @ts-expect-error — people-state-utils.js is plain JS without type declarations
import { buildPeoplePatch } from "../components/edit-people/hooks/people-state-utils.js";

describe("buildPeoplePatch", () => {
  it("sends only the changed fields for an edited existing person", () => {
    const people = [{ id: "a", name: "Alice", phones: ["x"], _changes: ["phones"] }];
    expect(buildPeoplePatch(people)).toEqual([{ id: "a", fields: { phones: ["x"] } }]);
  });

  it("sends empty fields for an untouched person", () => {
    expect(buildPeoplePatch([{ id: "a", name: "Alice" }])).toEqual([{ id: "a", fields: {} }]);
  });

  it("sends the whole entry for a new person", () => {
    const person = { id: "new1", name: "Bob", phones: [], _isNew: true, _changes: [] };
    expect(buildPeoplePatch([person])).toEqual([
      { id: "new1", fields: { id: "new1", name: "Bob", phones: [] } },
    ]);
  });

  it("sends the whole entry when the id changed (re-id)", () => {
    const person = { id: "canonical", name: "Bob", _changes: ["id", "name"] };
    expect(buildPeoplePatch([person])).toEqual([
      { id: "canonical", fields: { id: "canonical", name: "Bob" } },
    ]);
  });

  it("omits deleted people (the backend reads omission as a deletion)", () => {
    const people = [
      { id: "a", _changes: [] },
      { id: "b", _deleted: true, _changes: [] },
    ];
    expect(buildPeoplePatch(people).map((p: { id: string }) => p.id)).toEqual(["a"]);
  });

  it("preserves order", () => {
    const people = [{ id: "c", _changes: [] }, { id: "a", _changes: [] }, { id: "b", _changes: [] }];
    expect(buildPeoplePatch(people).map((p: { id: string }) => p.id)).toEqual(["c", "a", "b"]);
  });
});
