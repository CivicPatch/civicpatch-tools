import { describe, it, expect } from "vitest";
import { officeChangesIn } from "../components/person-editor/office-changes.js";

const card = (over = {}) =>
  ({
    personId: "p1",
    status: "changed",
    oldRecord: { id: "p1", memberships: [{ post_id: "council-1", post_label: "Council Member", label: "District 3" }] },
    newRecord: { id: "p1" },
    surviving: [],
    issues: [],
    ...over,
  }) as never;

describe("officeChangesIn", () => {
  it("is empty when nothing was picked", () =>
    expect(officeChangesIn([card()])).toEqual([]));

  it("reports a post pick that differs from what they already hold", () =>
    expect(
      officeChangesIn([card({ newRecord: { id: "p1", post_id: "mayor-1" } })]),
    ).toEqual([{ personId: "p1", postId: "mayor-1", label: "District 3" }]));

  it("keeps the held post when only the label changed", () =>
    expect(
      officeChangesIn([card({ newRecord: { id: "p1", membership_label: "Ward 2" } })]),
    ).toEqual([{ personId: "p1", postId: "council-1", label: "Ward 2" }]));

  it("is empty when the pick matches what they already hold", () =>
    expect(
      officeChangesIn([card({ newRecord: { id: "p1", post_id: "council-1" } })]),
    ).toEqual([]));

  it("carries an explicitly cleared label through as null, not as unchanged", () =>
    expect(
      officeChangesIn([card({ newRecord: { id: "p1", membership_label: null } })]),
    ).toEqual([{ personId: "p1", postId: "council-1", label: null }]));

  it("has nothing to attach a label-only edit to for someone with no current post", () =>
    expect(
      officeChangesIn([
        card({
          oldRecord: { id: "p1", memberships: [] },
          newRecord: { id: "p1", membership_label: "Ward 2" },
        }),
      ]),
    ).toEqual([]));

  it("skips a brand-new, not-yet-saved person — there is no membership yet to move", () =>
    expect(
      officeChangesIn([card({ oldRecord: null, newRecord: { id: "new-1", post_id: "mayor-1" } })]),
    ).toEqual([]));
});
