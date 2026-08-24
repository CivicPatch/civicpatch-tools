import { describe, it, expect } from "vitest";
import {
  acceptsByField,
  provenanceLabel,
  type PersonAssertion,
} from "../components/person-editor/field-provenance.js";

const assertion = (over: Partial<PersonAssertion> = {}): PersonAssertion => ({
  field_path: "name",
  kind: "accept",
  value: "Jane Doe",
  asserted_at: "2026-08-24T10:00:00+00:00",
  asserted_by_name: "Mango-chan",
  ...over,
});

describe("acceptsByField", () => {
  it("leaves rejects out — they explain an absence, so there is no value to tag", () => {
    const byField = acceptsByField([
      assertion({ field_path: "phones", kind: "reject", value: "(555) 0001" }),
    ]);
    expect(byField.get("phones")).toBeUndefined();
  });

  it("keeps every accept on a list field, since each element is its own row", () => {
    const byField = acceptsByField([
      assertion({ field_path: "phones", value: "(555) 0001" }),
      assertion({ field_path: "phones", value: "(555) 0002" }),
    ]);
    expect(byField.get("phones")).toHaveLength(2);
  });
});

describe("provenanceLabel", () => {
  // The date is rendered in the viewer's locale, so these match the name and not the format.
  it("says what happened, not what it implies", () =>
    // Publishing a card does not mean the reviewer read every field, so never "verified by".
    expect(provenanceLabel([assertion()])).toMatch(/^Published by Mango-chan, \S/));

  it("is null when nobody has published the field", () => {
    expect(provenanceLabel(undefined)).toBeNull();
    expect(provenanceLabel([])).toBeNull();
  });

  it("names the newest, so a list field names the publish and not an arbitrary element", () =>
    expect(
      provenanceLabel([
        assertion({ asserted_by_name: "Older", asserted_at: "2026-01-01T00:00:00+00:00" }),
        assertion({ asserted_by_name: "Newer", asserted_at: "2026-08-24T10:00:00+00:00" }),
      ]),
    ).toMatch(/^Published by Newer, /));

  it("still names the act when the user row is gone", () =>
    expect(provenanceLabel([assertion({ asserted_by_name: null })])).toMatch(
      /^Published by someone, /,
    ));
});
