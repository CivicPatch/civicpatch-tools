import { describe, it, expect } from "vitest";
import { getIssueDetail } from "../pages/issues-page/utils.js";
import { ISSUE_TYPE } from "../utils/issue-types.js";

const CHANGESET_ID = "req-123";

describe("getIssueDetail", () => {
  it("shows the merge error string for a merge_failed issue", () => {
    const data = { error: "Pull request is blocked", mergeable_state: "blocked" };
    expect(getIssueDetail(ISSUE_TYPE.MERGE_FAILED, CHANGESET_ID, data)).toBe("Pull request is blocked");
  });

  it("falls back to the issue key when a merge_failed issue has no error", () => {
    const data = { mergeable_state: null };
    expect(getIssueDetail(ISSUE_TYPE.MERGE_FAILED, CHANGESET_ID, data)).toBe(CHANGESET_ID);
  });

  it("falls back to the issue key when a merge_failed issue has no data", () => {
    expect(getIssueDetail(ISSUE_TYPE.MERGE_FAILED, CHANGESET_ID, null)).toBe(CHANGESET_ID);
  });

  it("does not surface a stored error for non-merge_failed types", () => {
    const data = { error: "some pipeline error" };
    expect(getIssueDetail(ISSUE_TYPE.PIPELINE_ERROR, CHANGESET_ID, data)).toBe(CHANGESET_ID);
  });

  it("appends person names for an unrecognized_role issue", () => {
    const data = { person_names: ["Jane Doe", "John Roe"] };
    expect(getIssueDetail(ISSUE_TYPE.UNRECOGNIZED_ROLE, "Mayor", data)).toBe("Mayor — Jane Doe, John Roe");
  });

  it("shows just the role for an unrecognized_role issue with no names", () => {
    expect(getIssueDetail(ISSUE_TYPE.UNRECOGNIZED_ROLE, "Mayor", { person_names: [] })).toBe("Mayor");
  });
});
