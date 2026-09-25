import { describe, it, expect } from "vitest";
import { officeEditsIn } from "../components/person-editor/office-edits.js";

// Both sides carry the office, as both sides of a real card do: since 19.3c the proposed row
// is the fold's and lists memberships exactly as the published one does. The fixture used to
// give the new side nothing but the reviewer's pick, which is the shape the proposal layer
// produced and no longer occurs.
const HELD = [{ post_id: "council-1", post_label: "Council Member", label: "District 3" }];

const card = (over: Record<string, unknown> = {}) =>
  ({
    personId: "p1",
    status: "changed",
    oldRecord: { id: "p1", memberships: HELD },
    newRecord: { id: "p1", memberships: HELD },
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
      officeEditsIn([card({ newRecord: { id: "p1", memberships: HELD, post_id: "mayor-1" } })]),
    ).toEqual([{ personId: "p1", postId: "mayor-1", membershipLabel: "District 3", organizationId: null }]));

  it("keeps an explicit label when both the post and the label changed", () =>
    expect(
      officeEditsIn([
        card({ newRecord: { id: "p1", memberships: HELD, post_id: "mayor-1", membership_label: "Acting" } }),
      ]),
    ).toEqual([{ personId: "p1", postId: "mayor-1", membershipLabel: "Acting", organizationId: null }]));

  it("keeps the held post when only the label changed", () =>
    expect(
      officeEditsIn([card({ newRecord: { id: "p1", memberships: HELD, membership_label: "Ward 2" } })]),
    ).toEqual([{ personId: "p1", postId: "council-1", membershipLabel: "Ward 2", organizationId: null }]));

  it("reads a null post as no pick, keeping the held post under a label edit", () =>
    expect(
      officeEditsIn([
        card({ newRecord: { id: "p1", memberships: HELD, post_id: null, membership_label: "Ward 2" } }),
      ]),
    ).toEqual([{ personId: "p1", postId: "council-1", membershipLabel: "Ward 2", organizationId: null }]));

  it("is empty when the pick matches what they already hold", () =>
    expect(
      officeEditsIn([card({ newRecord: { id: "p1", memberships: HELD, post_id: "council-1" } })]),
    ).toEqual([]));

  // Dates were person fields the fold never read; they are the membership's now.
  it("carries a changed term date on the office", () =>
    expect(
      officeEditsIn([card({ newRecord: { id: "p1", memberships: HELD, start_date: "2024-01" } })]),
    ).toEqual([
      {
        personId: "p1",
        postId: "council-1",
        membershipLabel: "District 3",
        startDate: "2024-01",
        endDate: null,
        organizationId: null,
      },
    ]));

  it("is empty when the dates match what they hold", () =>
    expect(
      officeEditsIn([
        card({
          newRecord: {
            id: "p1",
            memberships: [{ ...HELD[0], start_date: "2024" }],
            start_date: "2024",
          },
        }),
      ]),
    ).toEqual([]));

  it("reads an emptied date input as cleared", () =>
    expect(
      officeEditsIn([
        card({
          newRecord: { id: "p1", memberships: [{ ...HELD[0], end_date: "2028" }], end_date: "" },
        }),
      ])[0],
    ).toMatchObject({ endDate: null }));

  it("carries an explicitly cleared label through as null, not as unchanged", () =>
    expect(
      officeEditsIn([card({ newRecord: { id: "p1", memberships: HELD, membership_label: null } })]),
    ).toEqual([{ personId: "p1", postId: "council-1", membershipLabel: null, organizationId: null }]));

  it("has nothing to attach a label-only edit to for someone with no current post", () =>
    expect(
      officeEditsIn([
        card({
          oldRecord: { id: "p1", memberships: [] },
          newRecord: { id: "p1", memberships: [], membership_label: "Ward 2" },
        }),
      ]),
    ).toEqual([]));

  it("skips a brand-new, not-yet-saved person — there is no membership yet to move", () =>
    expect(
      officeEditsIn([card({ oldRecord: null, newRecord: { id: "new-1", post_id: "mayor-1" } })]),
    ).toEqual([]));
});

describe("officeEditsIn — against what the card shows, not what is published", () => {
  // The repro: a reviewer moved somebody to Mayor and saved, so the claim is in the changeset
  // and the proposed side derives Mayor — while the *published* side still says Council
  // Member, because nothing has published yet. Changing them back has to count as a change.
  const saved = (over = {}) =>
    ({
      personId: "p1",
      status: "changed",
      oldRecord: {
        id: "p1",
        memberships: [{ post_id: "council-1", post_label: "Council Member", label: null }],
      },
      newRecord: {
        id: "p1",
        memberships: [{ post_id: "mayor-1", post_label: "Mayor", label: null }],
      },
      surviving: [],
      issues: [],
      ...over,
    }) as never;

  it("sees a move back to the published office as a change", () => {
    const card = saved({
      newRecord: {
        id: "p1",
        memberships: [{ post_id: "mayor-1", post_label: "Mayor", label: null }],
        post_id: "council-1",
      },
    });

    expect(officeEditsIn([card])).toEqual([
      { personId: "p1", postId: "council-1", membershipLabel: null, organizationId: null },
    ]);
  });

  it("sees re-picking what the card already proposes as no change", () => {
    const card = saved({
      newRecord: {
        id: "p1",
        memberships: [{ post_id: "mayor-1", post_label: "Mayor", label: null }],
        post_id: "mayor-1",
      },
    });

    expect(officeEditsIn([card])).toEqual([]);
  });
});
