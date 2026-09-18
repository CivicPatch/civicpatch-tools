// The card's diff against the cases the server's diff also runs
// (tests/unit/core/test_roster_diff_contract.py), so the two cannot drift.
import { describe, it, expect } from "vitest";
import { POST_FIELD, changedFields } from "../components/fields/field-model.js";
import fixture from "./fixtures/person-diff-cases.json";

describe("the card's diff agrees with the server's", () => {
  for (const testCase of fixture.cases) {
    it(testCase.name, () => {
      const changed = changedFields(testCase.published as any, testCase.proposed as any)
        .map((change) => change.field.key)
        .filter((key) => key !== POST_FIELD);
      expect(changed).toEqual(testCase.changed);
    });
  }
});
