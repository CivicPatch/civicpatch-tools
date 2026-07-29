import { describe, it, expect } from "vitest";
// @ts-expect-error — diff-utils.js is plain JS without type declarations
import { computePeopleDiff, DiffType } from "../utils/diff-utils.js";

const person = (id: string, name = `Person ${id}`) => ({ id, name });
const never = () => false;

describe("computePeopleDiff — duplicate ids", () => {
  it("reports nothing when every id is unique", () => {
    const { duplicateIds } = computePeopleDiff([person("a")], [person("a")], never);
    expect(duplicateIds).toEqual([]);
  });

  it("reports an id that two proposed people share", () => {
    // This is what merge manufactures: matching consults aliases, so the next
    // scrape resolves both entries of a merged pair to the survivor's id.
    const { duplicateIds } = computePeopleDiff([], [person("a", "First"), person("a", "Second")], never);
    expect(duplicateIds).toEqual(["a"]);
  });

  it("reports an id that two existing records share", () => {
    const { duplicateIds } = computePeopleDiff([person("a"), person("a")], [], never);
    expect(duplicateIds).toEqual(["a"]);
  });

  it("still collapses to one entry — everything downstream is keyed by id", () => {
    // Keeping both would make the frozen field set, expansion, deletions and
    // restorations ambiguous, since all of them key on person id. The point of
    // the guard is that the loss is reported, not that it stops happening.
    const { diffEntries } = computePeopleDiff([], [person("a", "First"), person("a", "Second")], never);
    expect(diffEntries).toHaveLength(1);
    expect(diffEntries[0].person.name).toBe("Second");
    expect(diffEntries[0].type).toBe(DiffType.ADDED);
  });

  it("does not double-report an id duplicated on both sides", () => {
    const { duplicateIds } = computePeopleDiff(
      [person("a"), person("a")],
      [person("a"), person("a")],
      never,
    );
    expect(duplicateIds).toEqual(["a"]);
  });

  it("ignores people with no id at all", () => {
    const { duplicateIds } = computePeopleDiff([], [{ name: "No id" }, { name: "Also none" }], never);
    expect(duplicateIds).toEqual([]);
  });
});
