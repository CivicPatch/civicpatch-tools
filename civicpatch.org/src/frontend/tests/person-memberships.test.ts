import { describe, it, expect } from "vitest";
import {
  membershipTitle,
  membershipsByOrganization,
  pageWordings,
} from "../components/person-editor/person-memberships-model.js";
import { type RosterMembership } from "../schemas/roster-membership.js";

const membership = (over: Partial<RosterMembership> = {}): RosterMembership => ({
  id: "m1",
  person_id: "p1",
  post_id: "post1",
  organization_id: "org-council",
  organization_name: "City Council",
  post_label: "Council Member, District 3",
  label: null,
  source_labels: [],
  ...over,
});

describe("membershipsByOrganization", () => {
  it("gives a person in two bodies a section each", () => {
    // The whole reason the editor groups at all: two bodies are two commitments, and removing
    // somebody from one says nothing about the other.
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

// The three-state removal control ("closed" / "never held") was retired on 2026-09-23: a
// removal is the roster row dropping its office, covered by `roster-edit-payload.test.ts`.

describe("pageWordings", () => {
  it("drops a wording the title already says", () => {
    // Otherwise the row prints the same words twice and reads as two different posts.
    const row = membership({ source_labels: ["Council Member, District 3"] });

    expect(pageWordings(row, "Council Member, District 3")).toEqual([]);
  });

  it("keeps the page's own phrasing when it differs", () => {
    // The pair that prompted this: an abbreviation is a different string, not a different post.
    const row = membership({ source_labels: ["Mayor Pro Tem District 4"] });

    expect(pageWordings(row, "Mayor Pro Tempore, District 4")).toEqual([
      "Mayor Pro Tem District 4",
    ]);
  });

  it("lists each distinct wording once", () => {
    const row = membership({
      source_labels: ["Mayor Pro Tem", "Mayor Pro Tem", "Acting Mayor"],
    });

    expect(pageWordings(row, "Mayor Pro Tempore")).toEqual([
      "Mayor Pro Tem",
      "Acting Mayor",
    ]);
  });
});
