import { describe, it, expect } from "vitest";
import {
  membershipTitle,
  membershipsByOrganization,
  nextRemoval,
} from "../components/person-editor/person-memberships-model.js";
import {
  MEMBERSHIP_REMOVAL,
  type RosterMembership,
} from "../schemas/membership-removal.js";

const membership = (over: Partial<RosterMembership> = {}): RosterMembership => ({
  id: "m1",
  person_id: "p1",
  post_id: "post1",
  organization_id: "org-council",
  organization_name: "City Council",
  post_label: "Council Member, District 3",
  label: null,
  source_labels: [],
  removal_assertion: MEMBERSHIP_REMOVAL.NONE,
  not_a_member: false,
  ...over,
});

describe("membershipsByOrganization", () => {
  it("gives a person in two bodies a section each", () => {
    // The whole reason the editor groups at all: two bodies are two commitments, and closing
    // one says nothing about the other.
    const sections = membershipsByOrganization(
      [
        membership(),
        membership({
          id: "m2",
          organization_id: "org-mayor",
          organization_name: "Office of the Mayor",
          post_label: "Mayor",
        }),
      ],
      "p1",
    );

    expect(sections.map((section) => section.organizationName)).toEqual([
      "City Council",
      "Office of the Mayor",
    ]);
    expect(sections.map((section) => section.memberships.length)).toEqual([1, 1]);
  });

  it("leaves out everyone else's memberships", () => {
    // The read is per jurisdiction, so the payload carries the whole roster.
    const sections = membershipsByOrganization(
      [membership(), membership({ id: "m2", person_id: "p2" })],
      "p1",
    );

    expect(sections).toHaveLength(1);
    expect(sections[0].memberships.map((m) => m.id)).toEqual(["m1"]);
  });

  it("keeps two posts in one body together", () => {
    const sections = membershipsByOrganization(
      [membership(), membership({ id: "m2", post_label: "Council President" })],
      "p1",
    );

    expect(sections).toHaveLength(1);
    expect(sections[0].memberships).toHaveLength(2);
  });
});

describe("membershipTitle", () => {
  it("prefers the name a human gave over the composed one", () => {
    expect(
      membershipTitle(membership({ label: "Council President and Council Member" })),
    ).toBe("Council President and Council Member");
  });

  it("falls back to the composed post label", () => {
    expect(membershipTitle(membership())).toBe("Council Member, District 3");
  });
});

describe("nextRemoval", () => {
  it("withdraws the claim already made", () => {
    // What makes each button its own undo: there is no separate "take it back" act.
    expect(
      nextRemoval(MEMBERSHIP_REMOVAL.CLOSED, MEMBERSHIP_REMOVAL.CLOSED),
    ).toBe(MEMBERSHIP_REMOVAL.NONE);
  });

  it("swaps one claim for the other", () => {
    expect(
      nextRemoval(MEMBERSHIP_REMOVAL.CLOSED, MEMBERSHIP_REMOVAL.NEVER_HELD),
    ).toBe(MEMBERSHIP_REMOVAL.NEVER_HELD);
  });

  it("files the claim when nothing was chosen", () => {
    expect(nextRemoval(MEMBERSHIP_REMOVAL.NONE, MEMBERSHIP_REMOVAL.CLOSED)).toBe(
      MEMBERSHIP_REMOVAL.CLOSED,
    );
  });
});
