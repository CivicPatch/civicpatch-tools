import { describe, it, expect } from "vitest";
import { authorDisplayMode, markFreshEntries } from "../pages/home-page/recent-activity.js";

describe("authorDisplayMode", () => {
  it("names nobody for the system actor", () => {
    expect(authorDisplayMode(true, true)).toBe("none");
    expect(authorDisplayMode(true, false)).toBe("none");
  });

  it("links the name when the viewer can reach /~{username}", () => {
    expect(authorDisplayMode(false, true)).toBe("link");
  });

  it("still shows the name, just unlinked, when the viewer can't", () => {
    expect(authorDisplayMode(false, false)).toBe("text");
  });
});

describe("markFreshEntries", () => {
  it("marks nothing fresh on the very first load", () => {
    const fetched = [{ id: "a" }, { id: "b" }];
    expect(markFreshEntries(fetched, null)).toEqual([
      { id: "a", isFresh: false },
      { id: "b", isFresh: false },
    ]);
  });

  it("marks an id that wasn't in the previous set", () => {
    const fetched = [{ id: "a" }, { id: "b" }];
    expect(markFreshEntries(fetched, new Set(["a"]))).toEqual([
      { id: "a", isFresh: false },
      { id: "b", isFresh: true },
    ]);
  });

  it("marks nothing fresh once every id has already been seen", () => {
    const fetched = [{ id: "a" }, { id: "b" }];
    expect(markFreshEntries(fetched, new Set(["a", "b"]))).toEqual([
      { id: "a", isFresh: false },
      { id: "b", isFresh: false },
    ]);
  });
});
