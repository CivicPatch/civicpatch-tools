import { describe, it, expect } from "vitest";
import { focusedKey } from "../components/review-rail/rail-focus.js";
import { type FieldSpec } from "../components/review/field-model.js";

const FIELDS: FieldSpec[] = [
  { key: "name", label: "Name", type: "text", required: true },
  { key: "office.name", label: "Office", type: "text", required: true },
  { key: "emails", label: "Email", type: "multi" },
];

describe("focusedKey", () => {
  it("is null when the view opened on no field", () => {
    expect(focusedKey(FIELDS, null)).toBe(null);
  });

  it("takes the field the view asked for", () => {
    expect(focusedKey(FIELDS, { key: "emails" })).toBe("emails");
  });

  it("falls back to the first row when that field is not on screen", () => {
    expect(focusedKey(FIELDS, { key: "start_date" })).toBe("name");
  });

  it("is null when the rail is showing no fields at all", () => {
    expect(focusedKey([], { key: "name" })).toBe(null);
  });
});
