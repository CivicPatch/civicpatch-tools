import { describe, it, expect } from "vitest";
import {
  issueKey,
  issueChecksKey,
  isChecked,
  toggleCheck,
  resolvedFieldKeys,
  unresolvedIssues,
} from "../components/review/issue-checks.js";
import { type Issue } from "../components/fields/field-model.js";

const issue = (over: Partial<Issue> = {}): Issue => ({
  code: "new_official",
  message: "Extra official: Carol Extra",
  ...over,
});

describe("issueKey", () => {
  it("keys by content, so a rerun that recomputes issues keeps the tick", () => {
    expect(issueKey(issue())).toBe(issueKey({ ...issue() }));
  });

  it("gives two holders of one issue the same key", () => {
    // duplicate_unique_role names both people in a single message, so one tick
    // has to clear both anchors.
    const shared = { code: "duplicate_unique_role", message: "Role 'mayor' … Alice, Bob" };
    expect(issueKey({ ...shared, person_ids: ["alice"] })).toBe(
      issueKey({ ...shared, person_ids: ["bob"] }),
    );
  });

  it("separates issues that differ only by code", () => {
    expect(issueKey(issue({ code: "a" }))).not.toBe(issueKey(issue({ code: "b" })));
  });

  it("changes when the message is reworded — the tick correctly orphans", () => {
    expect(issueKey(issue())).not.toBe(issueKey(issue({ message: "Extra official: Carol" })));
  });
});

describe("issueChecksKey", () => {
  it("scopes ticks to one card", () => {
    expect(issueChecksKey("req-1")).not.toBe(issueChecksKey("req-2"));
    expect(issueChecksKey("req-1")).toBe("review:issue-checks:req-1");
  });
});

describe("toggleCheck", () => {
  it("ticks and unticks", () => {
    const one = toggleCheck({}, issue());
    expect(isChecked(one, issue())).toBe(true);
    expect(isChecked(toggleCheck(one, issue()), issue())).toBe(false);
  });

  it("stores nothing for an unticked issue, so the map is only what was done", () => {
    const ticked = toggleCheck({}, issue());
    expect(Object.keys(toggleCheck(ticked, issue()))).toEqual([]);
  });

  it("does not mutate the map it was given", () => {
    const before = {};
    toggleCheck(before, issue());
    expect(before).toEqual({});
  });

  it("leaves other ticks alone", () => {
    const checks = toggleCheck(toggleCheck({}, issue()), issue({ code: "other" }));
    expect(Object.keys(checks)).toHaveLength(2);
  });
});

describe("resolvedFieldKeys", () => {
  it("names the fields a ticked issue anchors to", () => {
    const anchored = issue({ code: "duplicate_unique_role", field: "post_id" });
    expect([...resolvedFieldKeys([anchored], toggleCheck({}, anchored))]).toEqual([
      "post_id",
    ]);
  });

  it("ignores an unticked issue", () => {
    const anchored = issue({ field: "post_id" });
    expect(resolvedFieldKeys([anchored], {}).size).toBe(0);
  });

  it("ignores a ticked issue that anchors to no field", () => {
    const rowLevel = issue();
    expect(resolvedFieldKeys([rowLevel], toggleCheck({}, rowLevel)).size).toBe(0);
  });
});

describe("unresolvedIssues", () => {
  it("drops a ticked issue, so the tick shows where the reviewer was looking", () => {
    const a = issue({ code: "a" });
    const b = issue({ code: "b" });
    expect(unresolvedIssues([a, b], toggleCheck({}, a))).toEqual([b]);
  });
});
