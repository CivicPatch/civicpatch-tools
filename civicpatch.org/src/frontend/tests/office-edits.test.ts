import { describe, it, expect } from "vitest";
import { officeEditsIn } from "../components/person-editor/office-edits.js";

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

describe("officeEditsIn", () => {
  it("is empty when nothing was picked", () =>
    expect(officeEditsIn([card()])).toEqual([]));

  // A label never names the post itself (core/membership_label.py's `render` no longer folds
  // it in), so changing which post someone holds has no bearing on it — it rides along as-is.
  it("keeps the held label when only the post changed", () =>
    expect(
      officeEditsIn([card({ newRecord: { id: "p1", post_id: "mayor-1" } })]),
    ).toEqual([{ personId: "p1", postId: "mayor-1", membershipLabel: "District 3" }]));

  it("keeps an explicit label when both the post and the label changed", () =>
    expect(
      officeEditsIn([
        card({ newRecord: { id: "p1", post_id: "mayor-1", membership_label: "Acting" } }),
      ]),
    ).toEqual([{ personId: "p1", postId: "mayor-1", membershipLabel: "Acting" }]));

  it("keeps the held post when only the label changed", () =>
    expect(
      officeEditsIn([card({ newRecord: { id: "p1", membership_label: "Ward 2" } })]),
    ).toEqual([{ personId: "p1", postId: "council-1", membershipLabel: "Ward 2" }]));

  it("is empty when the pick matches what they already hold", () =>
    expect(
      officeEditsIn([card({ newRecord: { id: "p1", post_id: "council-1" } })]),
    ).toEqual([]));

  it("carries an explicitly cleared label through as null, not as unchanged", () =>
    expect(
      officeEditsIn([card({ newRecord: { id: "p1", membership_label: null } })]),
    ).toEqual([{ personId: "p1", postId: "council-1", membershipLabel: null }]));

  it("has nothing to attach a label-only edit to for someone with no current post", () =>
    expect(
      officeEditsIn([
        card({
          oldRecord: { id: "p1", memberships: [] },
          newRecord: { id: "p1", membership_label: "Ward 2" },
        }),
      ]),
    ).toEqual([]));

  it("skips a brand-new, not-yet-saved person — there is no membership yet to move", () =>
    expect(
      officeEditsIn([card({ oldRecord: null, newRecord: { id: "new-1", post_id: "mayor-1" } })]),
    ).toEqual([]));
});
