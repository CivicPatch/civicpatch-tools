import { describe, it, expect } from "vitest";
import {
  selectableOcdids,
  toggleSelection,
} from "../pages/import-page/batch-selection.js";

const town = (ocdid: string, review_status: string) => ({
  jurisdiction_ocdid: ocdid,
  name: ocdid,
  request_id: `req-${ocdid}`,
  review_status,
  people: [],
});

describe("selectableOcdids", () => {
  it("offers only the towns still awaiting a decision", () => {
    const jurisdictions = [
      town("sherborn", "pending"),
      town("concord", "published"),
      town("lincoln", "dismissed"),
      town("acton", "pending"),
    ];

    expect(selectableOcdids(jurisdictions)).toEqual(["sherborn", "acton"]);
  });

  it("offers nothing once every town has been settled", () => {
    expect(selectableOcdids([town("concord", "published")])).toEqual([]);
  });
});

describe("toggleSelection", () => {
  it("adds a town that was not picked", () => {
    expect(toggleSelection(["sherborn"], "acton")).toEqual([
      "sherborn",
      "acton",
    ]);
  });

  it("removes a town that was", () => {
    expect(toggleSelection(["sherborn", "acton"], "sherborn")).toEqual([
      "acton",
    ]);
  });

  it("leaves the original alone", () => {
    const selected = ["sherborn"];
    toggleSelection(selected, "acton");
    expect(selected).toEqual(["sherborn"]);
  });
});
