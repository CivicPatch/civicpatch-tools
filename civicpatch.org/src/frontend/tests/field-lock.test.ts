import { describe, expect, it } from "vitest";
import {
  LOCK_HELD,
  LOCK_OVERRODE,
  fieldLock,
} from "../components/person-editor/field-provenance.ts";

const accept = (over = {}) => [
  {
    field_path: "phones",
    kind: "accept",
    value: "(253) 931-3041",
    created_at: "2026-09-06T10:00:00Z",
    created_by_name: "Mango-chan",
    ...over,
  },
];

describe("fieldLock", () => {
  it("is absent where nobody has stood behind the field", () => {
    // An auto-published jurisdiction asserts nothing, so its whole card carries no locks —
    // and that absence is the signal that nobody has ever reviewed the place.
    expect(fieldLock(undefined, undefined, ["(253) 931-3041"])).toBeNull();
    expect(fieldLock([], undefined, ["(253) 931-3041"])).toBeNull();
  });

  it("is quiet when the assertion agrees with the source", () => {
    // The common case: a review accepts every non-null value, so most locks disclose nothing.
    const lock = fieldLock(accept(), undefined, ["(253) 931-3041"]);

    expect(lock?.state).toBe(LOCK_HELD);
    expect(lock?.disclosure).toBeNull();
    // Not the formatted date: `toLocaleDateString` follows the runtime's locale, so pinning
    // "6 Sep 2026" fails wherever it renders "Sep 6, 2026" instead.
    expect(lock?.label).toContain("Published by Mango-chan");
  });

  it("says what the source had, when an accept replaced it", () => {
    const lock = fieldLock(accept(), ["(253) 931-3000"], ["(253) 931-3041"]);

    expect(lock?.state).toBe(LOCK_OVERRODE);
    expect(lock?.disclosure).toBe("Source said (253) 931-3000");
  });

  it("says what was removed, when a reject took one of several", () => {
    // The reject case, and the useful one: the number is gone from the field, so the lock is
    // the only place it still exists on screen.
    const lock = fieldLock(
      accept(),
      ["(253) 931-3041", "(253) 931-3039"],
      ["(253) 931-3041"],
    );

    expect(lock?.state).toBe(LOCK_OVERRODE);
    expect(lock?.disclosure).toBe("Removed (253) 931-3039");
  });

  it("still marks an override that left nothing to say", () => {
    // Every scraped value survived and an accept added one. Overridden, but with nothing
    // hidden — the lock is honest about the first without inventing the second.
    const lock = fieldLock(accept(), ["a@x.gov"], ["a@x.gov", "b@x.gov"]);

    expect(lock?.state).toBe(LOCK_OVERRODE);
    expect(lock?.disclosure).toBeNull();
  });

  it("reads a scalar the same way as a list", () => {
    const lock = fieldLock(accept({ field_path: "name" }), "Nancy Backus", "Nancy J. Backus");

    expect(lock?.disclosure).toBe("Source said Nancy Backus");
  });
});
