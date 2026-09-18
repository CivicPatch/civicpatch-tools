import { describe, it, expect } from "vitest";
import {
  REVIEW_FILTER,
  REVIEW_PAGE_SIZE,
  byChangeRank,
  filtered,
  pageCount,
  pageOf,
  selectableChangesetIds,
  changeSummary,
} from "../pages/import-page/batch-selection.js";
import { toggleSelection } from "../utils/toggle-selection.js";
import type { ChangeCounts } from "../pages/import-page/import-types.js";

const UNCHANGED: ChangeCounts = {
  added_people: 0,
  changed_people: 0,
  absent_memberships: 0,
};

const town = (
  ocdid: string,
  changeset_state: string,
  change_counts: ChangeCounts = UNCHANGED,
) => ({
  jurisdiction_ocdid: ocdid,
  name: ocdid,
  changeset_id: `req-${ocdid}`,
  changeset_state,
  people: 0,
  change_counts,
});

describe("selectableChangesetIds", () => {
  it("offers only the towns still awaiting a decision", () => {
    const jurisdictions = [
      town("sherborn", "open"),
      town("concord", "published"),
      town("lincoln", "dismissed"),
      town("acton", "open"),
    ];

    expect(selectableChangesetIds(jurisdictions)).toEqual(["req-sherborn", "req-acton"]);
  });

  it("offers nothing once every town has been settled", () => {
    expect(selectableChangesetIds([town("concord", "published")])).toEqual([]);
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

describe("paging", () => {
  const many = Array.from({ length: 60 }, (_, i) => `town-${i}`);

  it("splits into pages of REVIEW_PAGE_SIZE", () => {
    expect(pageOf(many, 0)).toHaveLength(REVIEW_PAGE_SIZE);
    expect(pageOf(many, 0)[0]).toBe("town-0");
    expect(pageOf(many, 1)[0]).toBe(`town-${REVIEW_PAGE_SIZE}`);
  });

  it("gives a short last page rather than padding", () => {
    expect(pageOf(many, 2)).toHaveLength(60 - REVIEW_PAGE_SIZE * 2);
  });

  it("always reports at least one page, even when empty", () => {
    expect(pageCount([])).toBe(1);
    expect(pageCount(many)).toBe(3);
  });
});

describe("byChangeRank", () => {
  it("puts absences first, then new people, then edits, then the unchanged", () => {
    const ordered = byChangeRank([
      town("unchanged", "open"),
      town("edited", "open", { ...UNCHANGED, changed_people: 1 }),
      town("added", "open", { ...UNCHANGED, added_people: 2 }),
      town("absent", "open", { ...UNCHANGED, absent_memberships: 1, added_people: 1 }),
    ]);

    expect(ordered.map((j) => j.name)).toEqual([
      "absent",
      "added",
      "edited",
      "unchanged",
    ]);
  });

  it("orders alphabetically within a group", () => {
    const ordered = byChangeRank([town("lincoln", "open"), town("acton", "open")]);

    expect(ordered.map((j) => j.name)).toEqual(["acton", "lincoln"]);
  });
});

describe("filtered", () => {
  const towns = [
    town("absent", "open", { ...UNCHANGED, absent_memberships: 1 }),
    town("added", "open", { ...UNCHANGED, added_people: 1 }),
    town("quiet", "open"),
  ];

  it("shows everything when no filter is picked", () => {
    expect(filtered(towns, [])).toHaveLength(3);
  });

  it("shows towns matching any picked filter", () => {
    const shown = filtered(towns, [REVIEW_FILTER.HAS_ABSENT, REVIEW_FILTER.UNCHANGED]);

    expect(shown.map((j) => j.name)).toEqual(["absent", "quiet"]);
  });
});

describe("changeSummary", () => {
  it("names only what is non-zero", () => {
    expect(
      changeSummary({ added_people: 2, changed_people: 0, absent_memberships: 1 }),
    ).toBe("2 added, 1 absent");
  });

  it("is empty when nothing changed", () => {
    expect(changeSummary(UNCHANGED)).toBe("");
  });
});
