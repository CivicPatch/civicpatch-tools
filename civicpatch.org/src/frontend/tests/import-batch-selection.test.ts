import { describe, it, expect } from "vitest";
import {
  REVIEW_FILTER,
  REVIEW_PAGE_SIZE,
  byChangeRank,
  filterCounts,
  filtered,
  localities,
  pageCount,
  pageOf,
  selectableChangesetIds,
  changeBadges,
} from "../pages/import-page/batch-selection.js";
import { toggleSelection } from "../utils/toggle-selection.js";
import type { ChangeCounts, RowError } from "../pages/import-page/import-types.js";

const UNCHANGED: ChangeCounts = {
  added_people: 0,
  changed_people: 0,
  absent_memberships: 0,
};

const card = (
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

const town = (
  ocdid: string,
  changeset_state: string,
  change_counts: ChangeCounts = UNCHANGED,
  errors: RowError[] = [],
) => ({
  jurisdiction_ocdid: ocdid,
  name: ocdid,
  review: card(ocdid, changeset_state, change_counts),
  errors,
});

const SHERBORN = "ocd-jurisdiction/country:us/state:ma/county:middlesex/place:sherborn/government";

const rowError = (ocdid: string, line: number | null = 3): RowError => ({
  line,
  jurisdiction_ocdid: ocdid,
  column: line == null ? null : "source_url",
  message: "required",
});

describe("localities", () => {
  it("puts each error on its locality's card", () => {
    const [sherborn] = localities([card(SHERBORN, "open")], [rowError(SHERBORN)]);

    expect(sherborn.review?.changeset_id).toBe(`req-${SHERBORN}`);
    expect(sherborn.errors).toHaveLength(1);
  });

  it("lists a locality the import rejected though it has no card", () => {
    const [blocked] = localities([], [rowError(SHERBORN), rowError(SHERBORN, 4)]);

    expect(blocked.review).toBeNull();
    expect(blocked.name).toBe("Sherborn");
    expect(blocked.errors).toHaveLength(2);
  });
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
  it("puts a locality with errors ahead of every change", () => {
    const ordered = byChangeRank([
      town("absent", "open", { ...UNCHANGED, absent_memberships: 1 }),
      town("broken", "open", UNCHANGED, [rowError("broken")]),
    ]);

    expect(ordered.map((j) => j.name)).toEqual(["broken", "absent"]);
  });

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
    expect(filtered(towns, null)).toHaveLength(3);
  });

  it("shows only the towns matching the picked filter", () => {
    expect(filtered(towns, REVIEW_FILTER.HAS_ABSENT).map((j) => j.name)).toEqual(["absent"]);
  });

  it("keeps a card-less locality under Errors and out of every change filter", () => {
    const [blocked] = localities([], [rowError(SHERBORN)]);

    expect(filtered([blocked], REVIEW_FILTER.ERRORS)).toHaveLength(1);
    expect(filtered([blocked], REVIEW_FILTER.UNCHANGED)).toHaveLength(0);
    expect(filtered([blocked], REVIEW_FILTER.OPEN)).toHaveLength(0);
  });
});

describe("an uncounted locality", () => {
  const uncounted = { ...town("quiet", "open"), review: { ...card("quiet", "open"), change_counts: null } };

  it("matches no change filter, since nothing is known about its changes", () => {
    expect(filtered([uncounted], REVIEW_FILTER.UNCHANGED)).toHaveLength(0);
    expect(filtered([uncounted], REVIEW_FILTER.HAS_ADDED)).toHaveLength(0);
  });

  it("still counts as open", () => {
    expect(filtered([uncounted], REVIEW_FILTER.OPEN)).toHaveLength(1);
  });
});

describe("filterCounts", () => {
  it("counts every filter over the whole batch", () => {
    const counts = filterCounts([
      town("absent", "open", { ...UNCHANGED, absent_memberships: 1, changed_people: 2 }),
      town("done", "published"),
      ...localities([], [rowError(SHERBORN)]),
    ]);

    expect(counts).toEqual({
      [REVIEW_FILTER.ERRORS]: 1,
      [REVIEW_FILTER.HAS_ABSENT]: 1,
      [REVIEW_FILTER.HAS_ADDED]: 0,
      [REVIEW_FILTER.HAS_CHANGED]: 1,
      [REVIEW_FILTER.UNCHANGED]: 1,
      [REVIEW_FILTER.OPEN]: 1,
    });
  });
});

describe("changeBadges", () => {
  it("names only what is non-zero, in the tally's colours", () => {
    expect(
      changeBadges({ added_people: 2, changed_people: 0, absent_memberships: 1 }),
    ).toEqual([
      { status: "added", label: "2 added" },
      { status: "removed", label: "1 absent" },
    ]);
  });

  it("says unchanged when nothing changed", () => {
    expect(changeBadges(UNCHANGED)).toEqual([{ status: "unchanged", label: "Unchanged" }]);
  });
});
