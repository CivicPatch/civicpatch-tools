import { describe, it, expect } from "vitest";
import { rosterEditPayload } from "../components/edit-people/roster-edit-payload.js";

const MAYOR = "11111111-1111-5111-8111-111111111111";
const CLERK = "22222222-2222-5222-8222-222222222222";

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
      [{ personId: "p1", postId: CLERK, membershipLabel: "Acting Clerk" }],
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

  it("lets a removal win over anything else said about that person", () => {
    const payload = rosterEditPayload(
      [patch("p1", { name: "Ann Lee" })],
      [{ personId: "p1", postId: CLERK, membershipLabel: null }],
      ["p1"],
    );

    expect(payload).toEqual([{ id: "p1", offices: [] }]);
  });

  it("sends one entry per person, whatever they appear in", () => {
    const payload = rosterEditPayload(
      [patch("p1", { name: "Ann Lee" }), patch("p2", { name: "Bo Nguyen" })],
      [{ personId: "p2", postId: MAYOR, membershipLabel: null }],
      ["p3"],
    );

    expect(payload.map((person) => person.id)).toEqual(["p1", "p2", "p3"]);
  });
});
