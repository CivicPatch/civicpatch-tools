import { describe, it, expect } from "vitest";
import { editorSummary, type EditorSummaryInput } from "../components/person-editor/editor-summary.js";
import { PersonStatus } from "../components/people/person-cards.js";
import {
  type Issue,
  type ScalarDiffState,
  type SurvivingField,
} from "../components/fields/field-model.js";

// `diff: false` is what makes a field context — always visible, never a change.
const field = (key: string, isContext = false) =>
  ({ key, label: key, diff: isContext ? false : undefined }) as SurvivingField["field"];

const surviving = (
  key: string,
  state: ScalarDiffState,
  over: { error?: string | null; isContext?: boolean } = {},
): SurvivingField => ({
  field: field(key, over.isContext ?? false),
  state,
  reason: "diff",
  error: over.error ?? null,
});

const issue = (message: string): Issue => ({ code: "duplicate", message });

const input = (over: Partial<EditorSummaryInput> = {}): EditorSummaryInput => ({
  status: PersonStatus.CHANGED,
  surviving: [],
  issues: [],
  isDirty: false,
  ...over,
});

describe("editorSummary", () => {
  it("counts only the fields that moved", () => {
    const result = editorSummary(
      input({
        surviving: [
          surviving("name", "changed"),
          surviving("labels", "same"),
          surviving("emails", "added"),
        ],
      }),
    );
    expect(result).toBe("2 fields changed");
  });

  it("says field, not fields, for one", () => {
    expect(editorSummary(input({ surviving: [surviving("name", "changed")] }))).toBe(
      "1 field changed",
    );
  });

  // Context fields are always on screen and never a change; counting them would
  // report work on a card that has none.
  it("does not count context fields as changes", () => {
    const result = editorSummary(
      input({ surviving: [surviving("source_urls", "changed", { isContext: true })] }),
    );
    expect(result).toBe("No changes");
  });

  it("describes a new person rather than counting their fields", () => {
    const result = editorSummary(
      input({
        status: PersonStatus.ADDED,
        surviving: [surviving("name", "added"), surviving("labels", "added")],
      }),
    );
    expect(result).toBe("New person");
  });

  it("names a departure instead of counting anything", () => {
    const removed = input({
      status: PersonStatus.REMOVED,
      surviving: [surviving("name", "changed")],
      issues: [issue("Check whether they left office")],
    });
    expect(editorSummary(removed)).toBe("Not found in this scrape");

    expect(editorSummary({ ...removed, status: PersonStatus.DELETED })).toBe(
      "You removed this person",
    );
  });

  it("adds what needs a decision, counting errors and issues together", () => {
    const result = editorSummary(
      input({
        surviving: [surviving("name", "changed"), surviving("emails", "changed", { error: "Bad" })],
        issues: [issue("Possible duplicate")],
      }),
    );
    expect(result).toBe("2 fields changed, 2 things to check");
  });

  // Clear-on-edit drops issue markers once the reviewer touches the card, so the
  // summary has to drop them too or it contradicts the rows beneath it.
  it("drops issues once the card is dirty, but keeps errors", () => {
    const dirty = input({
      surviving: [surviving("emails", "changed", { error: "Bad" })],
      issues: [issue("Possible duplicate")],
      isDirty: true,
    });
    expect(editorSummary(dirty)).toBe("1 field changed, 1 thing to check");
  });

  it("says so when there is nothing to review", () => {
    expect(editorSummary(input({ surviving: [surviving("name", "same")] }))).toBe("No changes");
  });
});
