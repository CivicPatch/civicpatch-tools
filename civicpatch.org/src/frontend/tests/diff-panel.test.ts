import { describe, it, expect } from "vitest";
import {
  FIELDS,
  getFieldValue,
  changedFields,
} from "../components/diff-panel/diff-fields.ts";

// The published side, as `get_people` sends it: `labels` from PERSON_LABELS, `division_ocdid`
// from PERSON_DIVISION. The proposed side is the same two keys, from `_render`.
const person = (over: Record<string, unknown> = {}) => ({
  name: "Ann Lee",
  labels: ["Council Member Place 2"],
  division_ocdid: "ocd-division/country:us/state:tx/place:alpha/ward:east",
  phones: [],
  emails: [],
  ...over,
});

describe("diff panel fields", () => {
  it("reads Post off labels, not a joined office name", () => {
    // The whole point of the move: `office.name` was these labels joined with " - " upstream,
    // and three spellings of one office read back as three offices.
    const row = FIELDS.find((f) => f.label === "Post");
    expect(row?.key).toBe("labels");
    expect(getFieldValue(person(), "labels")).toBe("Council Member Place 2");
  });

  it("reads Division off a flat field, not a nested one", () => {
    const row = FIELDS.find((f) => f.label === "Division");
    expect(row?.key).toBe("division_ocdid");
    expect(getFieldValue(person(), "division_ocdid")).toBe(
      "ocd-division/country:us/state:tx/place:alpha/ward:east",
    );
  });

  it("no longer walks a dotted path", () => {
    // `office.name` and `office.division_ocdid` were the only two, so a person still carrying
    // `office` reads as empty rather than being silently preferred over `labels`.
    expect(FIELDS.every((f) => !f.key.includes("."))).toBe(true);
    expect(getFieldValue({ office: { name: "Mayor" } }, "office.name")).toBe("");
  });

  it("joins several labels for display", () => {
    expect(getFieldValue(person({ labels: ["Mayor", "Council Member"] }), "labels")).toBe(
      "Mayor, Council Member",
    );
  });

  it("sees a label change the old office.name join would have hidden", () => {
    // Two spellings of one office differ as strings either way; what matters is that the
    // comparison is per-label rather than over one concatenation whose order can shift.
    const changed = changedFields(
      person({ labels: ["Councilmember Position 8"] }),
      person({ labels: ["Council Member Position 8"] }),
    );
    expect(changed.map((f) => f.label)).toEqual(["Post"]);
  });

  it("reports no change when both sides agree", () => {
    expect(changedFields(person(), person())).toEqual([]);
  });

  it("treats a missing field as empty rather than throwing", () => {
    expect(getFieldValue({}, "labels")).toBe("");
    expect(getFieldValue(undefined, "division_ocdid")).toBe("");
  });
});
