import { describe, it, expect } from "vitest";
import { rosterEditPayload } from "../components/edit-people/roster-edit-payload.js";

const MAYOR = "11111111-1111-5111-8111-111111111111";
const CLERK = "22222222-2222-5222-8222-222222222222";
const TRUSTEE = "33333333-3333-5333-8333-333333333333";

const patch = (id: string, fields: Record<string, unknown> = {}) => ({ id, fields });

describe("rosterEditPayload", () => {
  it("carries a person's changed fields through untouched", () => {
    expect(rosterEditPayload([patch("p1", { name: "Ann Lee" })], [], [])).toEqual([
      { id: "p1", fields: { name: "Ann Lee" } },
    ]);
  });

  it("turns an office pick into the whole set of posts that person holds", () => {
    const payload = rosterEditPayload(
      [patch("p1", { name: "Ann Lee" })],
      [{ personId: "p1", postId: CLERK, membershipLabel: "Acting Clerk", organizationId: null }],
      [],
    );

    expect(payload).toEqual([
      { id: "p1", fields: { name: "Ann Lee" }, offices: [{ id: CLERK, membership_label: "Acting Clerk" }] },
    ]);
  });

  it("reads a brand-new person's pick out of their fields", () => {
    // `officeEditsIn` only answers for somebody who already holds something, so an
    // addition's pick arrives as `post_id` among their fields.
    const payload = rosterEditPayload(
      [patch("new-1", { name: "Bo Nguyen", post_id: MAYOR, membership_label: "Mayor" })],
      [],
      [],
    );

    expect(payload).toEqual([
      {
        id: "new-1",
        fields: { name: "Bo Nguyen" },
        offices: [{ id: MAYOR, membership_label: "Mayor" }],
      },
    ]);
  });

  it("never sends the office fields as person fields", () => {
    const [person] = rosterEditPayload([patch("p1", { post_id: MAYOR, membership_label: "x" })], [], []);

    expect(person.fields).toEqual({});
  });

  it("removes somebody with an empty post set", () => {
    // The old patch dropped them and let the server infer removal from absence; saying it is
    // the whole difference between "not mentioned" and "holds nothing".
    expect(rosterEditPayload([], [], ["p9"])).toEqual([{ id: "p9", offices: [] }]);
  });

  it("lets a removal take the office while their other edits stand", () => {
    // This verified that a removal replaced everything else said about that person. It now
    // verifies that only their office goes: removing somebody from a body should not discard
    // a correction to their name, which is a fact about the person, not the seat.
    const payload = rosterEditPayload(
      [patch("p1", { name: "Ann Lee" })],
      [{ personId: "p1", postId: CLERK, membershipLabel: null, organizationId: null }],
      ["p1"],
    );

    expect(payload).toEqual([{ id: "p1", fields: { name: "Ann Lee" }, offices: [] }]);
  });

  it("sends one entry per person, whatever they appear in", () => {
    const payload = rosterEditPayload(
      [patch("p1", { name: "Ann Lee" }), patch("p2", { name: "Bo Nguyen" })],
      [{ personId: "p2", postId: MAYOR, membershipLabel: null, organizationId: null }],
      ["p3"],
    );

    expect(payload.map((person) => person.id)).toEqual(["p1", "p2", "p3"]);
  });

  it("keeps every body's office when somebody sits on two", () => {
    // `offices` is the whole set. Sending only the last would tell the server they hold
    // nothing in the other body, and it would reject that post.
    const payload = rosterEditPayload(
      [patch("p1", { name: "Ann Lee" })],
      [
        { personId: "p1", postId: MAYOR, membershipLabel: null, organizationId: null },
        { personId: "p1", postId: CLERK, membershipLabel: "Acting Clerk", organizationId: null },
      ],
      [],
    );

    expect(payload[0].offices).toEqual([
      { id: MAYOR, membership_label: null },
      { id: CLERK, membership_label: "Acting Clerk" },
    ]);
  });

  it("lets a later edit for the same body win", () => {
    const payload = rosterEditPayload(
      [patch("p1", { name: "Ann Lee" })],
      [
        { personId: "p1", postId: MAYOR, membershipLabel: null, organizationId: null },
        { personId: "p1", postId: MAYOR, membershipLabel: "Acting Mayor", organizationId: null },
      ],
      [],
    );

    expect(payload[0].offices).toEqual([{ id: MAYOR, membership_label: "Acting Mayor" }]);
  });

  it("keeps the offices a reviewer did not touch", () => {
    // The editor only reports what changed. Sending the changed office alone would tell the
    // server they hold nothing in their other body, and it would reject that post.
    const held = new Map([
      [
        "p1",
        [
          { id: MAYOR, membership_label: null, organizationId: "org-council" },
          { id: TRUSTEE, membership_label: null, organizationId: "org-schools" },
        ],
      ],
    ]);

    const payload = rosterEditPayload(
      [patch("p1", {})],
      [
        {
          personId: "p1",
          postId: CLERK,
          membershipLabel: "Acting Clerk",
          organizationId: "org-council",
        },
      ],
      [],
      held,
    );

    expect(payload[0].offices).toEqual([
      { id: TRUSTEE, membership_label: null },
      { id: CLERK, membership_label: "Acting Clerk" },
    ]);
  });

  it("drops the office somebody moved out of, within the body they moved in", () => {
    // A move changes the post, so replacing by post id would leave both.
    const held = new Map([
      [
        "p1",
        [{ id: MAYOR, membership_label: null, organizationId: "org-council" }],
      ],
    ]);

    const payload = rosterEditPayload(
      [patch("p1", {})],
      [
        {
          personId: "p1",
          postId: CLERK,
          membershipLabel: null,
          organizationId: "org-council",
        },
      ],
      [],
      held,
    );

    expect(payload[0].offices).toEqual([{ id: CLERK, membership_label: null }]);
  });

  it("removing one body's row leaves the other body's office alone", () => {
    const held = new Map([
      [
        "p1",
        [
          { id: MAYOR, membership_label: null, organizationId: "org-council" },
          { id: TRUSTEE, membership_label: null, organizationId: "org-schools" },
        ],
      ],
    ]);

    const payload = rosterEditPayload([], [], ["p1:org-council"], held);

    expect(payload).toEqual([
      { id: "p1", offices: [{ id: TRUSTEE, membership_label: null }] },
    ]);
  });

  it("removing every row leaves them holding nothing", () => {
    // Which is how "off the roster entirely" says itself: no special case for it.
    const held = new Map([
      [
        "p1",
        [
          { id: MAYOR, membership_label: null, organizationId: "org-council" },
          { id: TRUSTEE, membership_label: null, organizationId: "org-schools" },
        ],
      ],
    ]);

    const payload = rosterEditPayload(
      [],
      [],
      ["p1:org-council", "p1:org-schools"],
      held,
    );

    expect(payload).toEqual([{ id: "p1", offices: [] }]);
  });
});
