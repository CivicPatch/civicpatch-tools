import { describe, it, expect } from "vitest";
import { mergedBadge, withMergesStaying } from "../components/review-overview/overview-model.js";

const card = (personId: string, name: string) =>
  ({ personId, status: "removed", newRecord: null, oldRecord: { id: personId, name } }) as never;

describe("merges on the overview", () => {
  const merged = new Map([["di", "cy"]]);
  const cards = [card("cy", "Cy Council"), card("di", "Di Board")];

  it("names who absorbed a merged-away row", () => {
    expect(mergedBadge(cards[1], merged, cards)).toBe("Merged into Cy Council");
    expect(mergedBadge(cards[0], merged, cards)).toBeNull();
  });

  it("keeps a merged-away row from counting as a departure", () => {
    const entries = [{ card: cards[1], office: {} as never, leaving: true }];
    expect(withMergesStaying(entries, merged).map((entry) => entry.leaving)).toEqual([false]);
    expect(withMergesStaying(entries, new Map()).map((entry) => entry.leaving)).toEqual([true]);
  });
});
