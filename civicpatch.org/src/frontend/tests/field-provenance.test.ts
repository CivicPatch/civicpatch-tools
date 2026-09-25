import { describe, it, expect } from "vitest";
import {
  acceptsByField,
  provenanceLabel,
  type PersonClaim,
} from "../components/person-editor/field-provenance.js";

const claim = (over: Partial<PersonClaim> = {}): PersonClaim => ({
  field_path: "name",
  kind: "accept",
  value: "Jane Doe",
  created_at: "2026-08-24T10:00:00+00:00",
  created_by_name: "Mango-chan",
  ...over,
});

describe("acceptsByField", () => {
  it("leaves rejects out — they explain an absence, so there is no value to tag", () => {
    const byField = acceptsByField([
      claim({ field_path: "phones", kind: "reject", value: "(555) 0001" }),
    ]);
    expect(byField.get("phones")).toBeUndefined();
  });

  it("keeps every accept on a list field, since each element is its own row", () => {
    const byField = acceptsByField([
      claim({ field_path: "phones", value: "(555) 0001" }),
      claim({ field_path: "phones", value: "(555) 0002" }),
    ]);
    expect(byField.get("phones")).toHaveLength(2);
  });
});

describe("provenanceLabel", () => {
  // The date is rendered in the viewer's locale, so these match the name and not the format.
  it("says what happened, not what it implies", () =>
    // Publishing a card does not mean the reviewer read every field, so never "verified by".
    expect(provenanceLabel([claim()])).toMatch(/^Published by Mango-chan, \S/));

  it("is null when nobody has published the field", () => {
    expect(provenanceLabel(undefined)).toBeNull();
    expect(provenanceLabel([])).toBeNull();
  });

  it("names the newest, so a list field names the publish and not an arbitrary element", () =>
    expect(
      provenanceLabel([
        claim({ created_by_name: "Older", created_at: "2026-01-01T00:00:00+00:00" }),
        claim({ created_by_name: "Newer", created_at: "2026-08-24T10:00:00+00:00" }),
      ]),
    ).toMatch(/^Published by Newer, /));

  it("still names the act when the user row is gone", () =>
    expect(provenanceLabel([claim({ created_by_name: null })])).toMatch(
      /^Published by someone, /,
    ));
});
